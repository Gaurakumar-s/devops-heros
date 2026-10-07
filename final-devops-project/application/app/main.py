"""TaskBoard API - Session 21 final DevOps project.

Endpoints
  GET  /            service info
  GET  /health      liveness  (process is alive)
  GET  /ready       readiness (database reachable)
  GET  /metrics     Prometheus metrics
  GET  /api/tasks   list tasks
  POST /api/tasks   create {"title": "..."}
  PUT  /api/tasks/<id>   update {"done": true}
  DELETE /api/tasks/<id> delete  (needs header X-Admin-Token == ADMIN_TOKEN)
"""
import os
import sqlite3
import time
from contextlib import closing

from flask import Flask, jsonify, request, g
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

APP_NAME = os.environ.get("APP_NAME", "taskboard")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
DATA_DIR = os.environ.get("DATA_DIR", "/tmp/taskboard-data")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
DB_PATH = os.path.join(DATA_DIR, "tasks.db")
STARTED_AT = time.time()

REQUESTS = Counter("taskboard_requests_total", "HTTP requests", ["method", "endpoint", "status"])
LATENCY = Histogram("taskboard_request_seconds", "Request latency", ["endpoint"])
TASKS = Gauge("taskboard_tasks", "Number of tasks", ["state"])


def create_app():
    app = Flask(APP_NAME)
    os.makedirs(DATA_DIR, exist_ok=True)
    with closing(connect()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)")
        c.commit()

    @app.before_request
    def _start():
        g.t0 = time.time()

    @app.after_request
    def _record(resp):
        ep = request.url_rule.rule if request.url_rule else "unknown"
        REQUESTS.labels(request.method, ep, resp.status_code).inc()
        LATENCY.labels(ep).observe(time.time() - g.t0)
        return resp

    @app.get("/")
    def index():
        return jsonify(app=APP_NAME, environment=ENVIRONMENT, uptime_seconds=round(time.time() - STARTED_AT, 1),
                       endpoints=["/health", "/ready", "/metrics", "/api/tasks"])

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/ready")
    def ready():
        try:
            with closing(connect()) as c:
                c.execute("SELECT 1")
            return jsonify(status="ready", database=DB_PATH)
        except Exception as exc:  # pragma: no cover
            return jsonify(status="not-ready", error=str(exc)), 503

    @app.get("/metrics")
    def metrics():
        with closing(connect()) as c:
            done = c.execute("SELECT COUNT(*) FROM tasks WHERE done=1").fetchone()[0]
            open_ = c.execute("SELECT COUNT(*) FROM tasks WHERE done=0").fetchone()[0]
        TASKS.labels("done").set(done)
        TASKS.labels("open").set(open_)
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.get("/api/tasks")
    def list_tasks():
        with closing(connect()) as c:
            rows = c.execute("SELECT id, title, done, created_at FROM tasks ORDER BY id").fetchall()
        return jsonify([row_to_task(r) for r in rows])

    @app.post("/api/tasks")
    def create_task():
        body = request.get_json(silent=True) or {}
        title = (body.get("title") or "").strip()
        if not title:
            return jsonify(error="title is required"), 400
        with closing(connect()) as c:
            cur = c.execute("INSERT INTO tasks (title, done, created_at) VALUES (?, 0, ?)", (title, time.time()))
            c.commit()
            row = c.execute("SELECT id, title, done, created_at FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(row_to_task(row)), 201

    @app.put("/api/tasks/<int:task_id>")
    def update_task(task_id):
        body = request.get_json(silent=True) or {}
        with closing(connect()) as c:
            if c.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone() is None:
                return jsonify(error="not found"), 404
            if "title" in body:
                c.execute("UPDATE tasks SET title=? WHERE id=?", (str(body["title"]).strip(), task_id))
            if "done" in body:
                c.execute("UPDATE tasks SET done=? WHERE id=?", (1 if body["done"] else 0, task_id))
            c.commit()
            row = c.execute("SELECT id, title, done, created_at FROM tasks WHERE id=?", (task_id,)).fetchone()
        return jsonify(row_to_task(row))

    @app.delete("/api/tasks/<int:task_id>")
    def delete_task(task_id):
        if not ADMIN_TOKEN or request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
            return jsonify(error="admin token required"), 401
        with closing(connect()) as c:
            deleted = c.execute("DELETE FROM tasks WHERE id=?", (task_id,)).rowcount
            c.commit()
        if not deleted:
            return jsonify(error="not found"), 404
        return "", 204

    return app


def connect():
    return sqlite3.connect(DB_PATH)


def row_to_task(r):
    return {"id": r[0], "title": r[1], "done": bool(r[2]), "created_at": r[3]}


if __name__ == "__main__":
    create_app().run(host=os.environ.get("FLASK_HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8080")))
