# Campus Safety Hazard Reporting System — container image.
# Build:  docker build -t campus-safety .
# Tests:  docker run --rm campus-safety python -m unittest discover -s tests -t . -v
# App:    docker run -it --rm --env-file .env -v campus-safety-data:/data campus-safety
FROM python:3.12-slim

# No .pyc files, unbuffered output (prompts appear immediately), data kept in /data.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HAZARD_DATA_DIR=/data

WORKDIR /app

# Install dependencies first so Docker can cache this layer between code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user; it owns the app folder (uploads/) and the data volume.
RUN useradd --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

VOLUME ["/data"]

CMD ["python", "main.py"]
