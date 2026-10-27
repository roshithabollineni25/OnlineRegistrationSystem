FROM python:3.12-slim

# Install PostgreSQL runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifest and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Run DB migration and start Gunicorn production server
ENV FLASK_ENV=production
ENV PORT=5000
EXPOSE 5000

CMD ["sh", "-c", "python migrate.py --init && gunicorn --bind 0.0.0.0:${PORT} --workers 4 --threads 2 app:app"]
