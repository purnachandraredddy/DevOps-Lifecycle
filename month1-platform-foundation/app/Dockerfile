FROM python:3.12-slim

WORKDIR /app

# Install dependencies first — Docker layer caching means this layer
# is only rebuilt when requirements.txt changes, not on every code change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Expose is documentation only — it does not publish the port.
# The actual port binding happens in the CMD below.
EXPOSE 8000

# uvicorn listens on 0.0.0.0 (all interfaces), not 127.0.0.1 (loopback only).
# Binding to 127.0.0.1 inside a container means the port is unreachable from
# outside the container — a common mistake that causes "connection refused" errors.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
