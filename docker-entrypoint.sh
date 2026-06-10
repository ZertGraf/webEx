#!/bin/sh
set -e

# Wait for the (shared) MySQL to accept connections, then create tables.
# `init-db` is just create_all and `seed` guards itself, so both are safe to
# run on every start.
i=0
until flask init-db; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "database not reachable after 30 attempts, giving up"
    exit 1
  fi
  echo "database not ready, retry $i/30..."
  sleep 2
done

flask seed || true

exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 60 wsgi:app
