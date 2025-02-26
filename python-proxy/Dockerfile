FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create cache directory
RUN mkdir -p /cache/html /cache/json /cache/css /cache/js /cache/other

COPY app.py .

ENV CACHE_DIR=/cache
ENV CACHE_TTL=600
ENV CACHE_CLEANUP_INTERVAL=3600

EXPOSE 8080

CMD ["python", "app.py"]
