#!/usr/bin/env bash
# Set up Leon on a fresh Ubuntu 24.04 server (Vultr Cloud Compute, 2 GB RAM or more) and start it.
# Run as root from the repository folder:   bash deploy/vultr-setup.sh [domain]
# Without a domain the site gets https://<server-ip>.sslip.io, which points back at this server.
# Safe to run again: it keeps existing keys and data, rebuilds and restarts.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this as root (or with sudo)." >&2
  exit 1
fi

COMPOSE="docker compose -f docker-compose.prod.yml"

set_env() {
  if grep -q "^$1=" .env; then
    sed -i "s|^$1=.*|$1=$2|" .env
  else
    echo "$1=$2" >> .env
  fi
}

current() {
  grep "^$1=" .env | head -1 | cut -d= -f2- || true
}

echo "== Swap (keeps the app build from running out of memory)"
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

echo "== Docker"
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  apt-get update -q
  apt-get install -y -q docker.io docker-compose-v2
  systemctl enable --now docker
fi

echo "== Firewall: web traffic on 80 and 443"
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw allow 443/udp >/dev/null
fi

echo "== Settings (.env)"
[ -f .env ] || cp .env.example .env
site="${1:-$(current SITE_ADDRESS)}"
if [ -z "$site" ]; then
  ip="$(hostname -I | awk '{print $1}')"
  site="${ip//./-}.sslip.io"
fi
set_env SITE_ADDRESS "$site"
[ -n "$(current POSTGRES_PASSWORD)" ] || set_env POSTGRES_PASSWORD "$(openssl rand -hex 24)"
set_env DEMO_MODE true
set_env VITE_DEMO_MODE true
set_env USE_CELERY_BEAT true
set_env VITE_API_URL ""

secret="$(current DJANGO_SECRET_KEY)"
if [ -z "$secret" ] || [ "$secret" = "change-me-to-a-long-random-string" ]; then
  $COMPOSE build web
  keys="$($COMPOSE run --rm --no-deps -e DJANGO_SETTINGS_MODULE=config.settings.dev web python manage.py init_env)"
  set_env DJANGO_SECRET_KEY "$(echo "$keys" | grep '^DJANGO_SECRET_KEY=' | cut -d= -f2-)"
  if [ -z "$(current VAPID_PRIVATE_KEY)" ]; then
    set_env VAPID_PUBLIC_KEY "$(echo "$keys" | grep '^VAPID_PUBLIC_KEY=' | cut -d= -f2-)"
    set_env VAPID_PRIVATE_KEY "$(echo "$keys" | grep '^VAPID_PRIVATE_KEY=' | cut -d= -f2-)"
  fi
fi
chmod 600 .env

echo "== Build and start (the first build takes a few minutes)"
$COMPOSE up -d --build

if [ ! -f .seeded ]; then
  echo "== Demo data"
  $COMPOSE exec -T web python manage.py seed_demo --sample-content
  touch .seeded
fi

echo
echo "Leon is starting at https://$site"
echo "The HTTPS certificate can take a minute on the first visit."
echo "To turn on AI: put your key in AI_API_KEY in .env (nano .env), then run:"
echo "  $COMPOSE up -d"
