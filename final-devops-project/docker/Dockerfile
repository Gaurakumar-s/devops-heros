# Multi-stage build: dependencies compiled in "builder", only the runtime copied into the final image.
FROM public.ecr.aws/docker/library/python:3.12-alpine AS builder
WORKDIR /build
COPY application/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM public.ecr.aws/docker/library/python:3.12-alpine
LABEL org.opencontainers.image.source="https://github.com/Gaurakumar-s/devops-heros"
WORKDIR /app
COPY --from=builder /install /usr/local
COPY application/app ./app
RUN addgroup -S taskboard && adduser -S -G taskboard taskboard \
 && mkdir -p /data && chown taskboard:taskboard /data
USER taskboard
ENV FLASK_HOST=0.0.0.0 PORT=8080 DATA_DIR=/data
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s CMD wget -q -O- http://127.0.0.1:8080/health || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--access-logfile", "-", "app.main:create_app()"]
