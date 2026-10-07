FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY app ./app

# the container must listen on all interfaces so Kubernetes/Docker can reach it
ENV FLASK_HOST=0.0.0.0 PORT=5001

EXPOSE 5001

CMD ["python", "app/app.py"]