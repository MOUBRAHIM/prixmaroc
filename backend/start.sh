#!/bin/sh

echo "=== PrixMaroc Backend Starting ==="
echo "DATABASE_URL prefix: $(echo ${DATABASE_URL} | cut -c1-60)"

# Wake up Neon (cold start) — connect to TCP first
echo "Checking database connectivity..."
python -c "
import os, socket, time, sys
from urllib.parse import urlparse

db_url = os.environ.get('DATABASE_URL', '')
parsed = urlparse(db_url)
host = parsed.hostname or 'localhost'
port = parsed.port or 5432

if not host or 'railway.internal' in host:
    print(f'Skipping internal host ({host})')
    sys.exit(0)

print(f'Connecting to {host}:{port} ...')
for i in range(10):
    try:
        s = socket.create_connection((host, port), timeout=5)
        s.close()
        print(f'DB reachable after {i*5}s — waiting 3s for cold-start init...')
        time.sleep(3)
        sys.exit(0)
    except Exception as e:
        print(f'  attempt {i+1}/10: {e}')
        time.sleep(5)
print('DB unreachable after 50s, continuing anyway...')
"

echo "Running Alembic migrations..."
timeout 90 alembic upgrade head
ALEMBIC_EXIT=$?
if [ $ALEMBIC_EXIT -ne 0 ]; then
    echo "WARNING: Alembic exited with code $ALEMBIC_EXIT — starting uvicorn anyway"
fi

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
