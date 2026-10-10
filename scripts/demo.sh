#!/usr/bin/env sh
# Run migrations and seed data without Docker. Usage: scripts/demo.sh
set -e
cd "$(dirname "$0")/../backend"
python manage.py migrate --noinput
python manage.py seed_demo
