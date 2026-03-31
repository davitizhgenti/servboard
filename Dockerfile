FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psutil and flet
RUN apt-get update && apt-get install -y \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache_dir -r requirements.txt

COPY . .

EXPOSE 3000
ENV FLET_SERVER_PORT=3000
ENV WEB_MODE=1

CMD ["python", "main.py"]


