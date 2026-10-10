#!/usr/bin/env sh
# Without Docker: create .env if needed, run migrations and load the demo data.
# Run from the repo root with the backend virtualenv active: sh scripts/demo.sh
set -e
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
cd backend
python manage.py init_env ../.env
python manage.py migrate --noinput
python manage.py seed_demo
