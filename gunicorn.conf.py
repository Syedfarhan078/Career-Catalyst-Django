"""
Gunicorn configuration for CareerCatalyst on Render.

Resource Profile:
- Optimized for Render Standard / Free Web Services (512MB RAM, shared vCPU).
- Uses the 'gthread' threaded worker engine to maximize concurrent I/O throughput
  while keeping the memory footprint well within the 512MB limit (~180MB - 240MB).
- Every parameter is easily tunable via environment variables without requiring code changes.
"""

import os
import multiprocessing

# --- Worker & Thread Concurrency ---
# 2 workers x 4 threads = 8 concurrent request slots
# Tunable via WEB_CONCURRENCY and GUNICORN_THREADS in Render Dashboard
workers = int(os.getenv("WEB_CONCURRENCY", 2))
threads = int(os.getenv("GUNICORN_THREADS", 4))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

# --- Connection Queuing ---
# Backlog: Number of unaccepted connections that the system will queue
backlog = int(os.getenv("GUNICORN_BACKLOG", 2048))

# --- Timeouts ---
# Timeout for worker silent death; 60s gives adequate headroom for PDF rendering
timeout = int(os.getenv("GUNICORN_TIMEOUT", 60))
# Graceful timeout for in-flight requests during rolling restarts
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))
# HTTP keep-alive timeout
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 2))

# --- Worker Lifecycle & Memory Recycling ---
# Recycles worker processes after handling N requests to prevent memory fragmentation
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 100))

# --- Heartbeat & Temporary Directory ---
# Use in-memory filesystem (/dev/shm) on Linux to avoid disk I/O blocking
if os.path.exists("/dev/shm"):
    worker_tmp_dir = "/dev/shm"

# --- Process Naming & Logging ---
proc_name = "careercatalyst_gunicorn"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
accesslog = "-"  # stdout
errorlog = "-"   # stderr
