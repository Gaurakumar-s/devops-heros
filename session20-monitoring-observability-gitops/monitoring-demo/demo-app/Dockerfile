FROM public.ecr.aws/docker/library/python:3.12-alpine
WORKDIR /app
RUN pip install --no-cache-dir prometheus_client==0.21.1
COPY app.py .
EXPOSE 8000
CMD ["python", "app.py"]
