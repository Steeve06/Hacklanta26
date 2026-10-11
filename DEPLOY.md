# Deploying Leon

Nothing here is deployed for you. There are two ways to run Leon in production: everything on one Vultr server (the quickest, below), or the backend on Render and the frontend on Vercel. Vercel can't run Celery workers or long AI jobs, so on that route the backend goes to Render.

## One server on Vultr

`docker-compose.prod.yml` runs the whole app on one machine: Postgres, Redis, Django (gunicorn, production settings), the Celery worker and Beat, and Caddy, which serves the built app and gets an HTTPS certificate on its own.

1. In Vultr, deploy a **Cloud Compute** server with **Ubuntu 24.04** and at least **2 GB of RAM**. Note its IP address and root password.
2. Connect: `ssh root@<server-ip>` (or the Vultr web console).
3. Get the code and run the setup script:
   ```sh
   git clone https://github.com/Steeve06/Hacklanta26.git leon
   cd leon
   bash deploy/vultr-setup.sh
   ```
   It adds swap, installs Docker, opens ports 80 and 443, writes `.env` with a new secret key, push keys and database password, builds, starts, and loads the sample demo data. The first run takes about 10 minutes.
4. Open the address it prints, `https://<ip-with-dashes>.sslip.io`. With your own domain, point its A record at the server and run `bash deploy/vultr-setup.sh your.domain` instead.
5. To turn on AI, set `AI_API_KEY` in `.env` (`nano .env`), then `docker compose -f docker-compose.prod.yml up -d`.

To update after pushing new code: `git pull && bash deploy/vultr-setup.sh`. To reset the demo data: `docker compose -f docker-compose.prod.yml exec web python manage.py seed_demo --sample-content`. Logs: `docker compose -f docker-compose.prod.yml logs -f web worker`.

The script keeps `DEMO_MODE=true` so the admin's demo controls work during judging. Set it to `false` in `.env` for real use.

## What runs where

| Piece | Where | From |
| --- | --- | --- |
| Django API (gunicorn) | Render web service `pulse-api` | `render.yaml` |
| Celery worker | Render background worker `pulse-worker` | `render.yaml` |
| Periodic jobs every 10 min | Render cron job `pulse-periodic` (`manage.py run_periodic`) | `render.yaml` |
| PostgreSQL | Render Postgres `pulse-db` | `render.yaml` |
| Redis | Render Key Value `pulse-kv` | `render.yaml` |
| React app | Vercel, root directory `frontend` | `frontend/vercel.json` |

The web service and worker use the Starter plan (the web service needs a paid plan for the disk that stores uploads), and Render has no free plan for cron jobs. Postgres and Key Value use the free plans. Check Render's current pricing before you apply the Blueprint.

## 1. Backend on Render

1. Push the repo to GitHub (see GIT.md).
2. Generate push keys locally: `cd backend && python manage.py init_env` prints a secret key and a VAPID key pair. You only need the two VAPID values; Render generates the secret key.
3. In Render, choose **New > Blueprint**, pick the repo, and Render reads `render.yaml`.
4. Fill in the values it asks for:
   - `AI_API_KEY`: your Anthropic key, or leave empty to run on fallbacks.
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`: from step 2. `VAPID_SUBJECT`: `mailto:` plus your address.
   - `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL`: your Vercel URL, e.g. `https://pulse-yourname.vercel.app`. Fill these in after step 2 of the frontend if you don't know the URL yet.
   - `EMAIL_*`: SMTP settings for the email fallback (Resend's SMTP works). Leave `EMAIL_BACKEND` empty to log emails instead.
5. Apply. Migrations run before each deploy. Check `https://pulse-api.onrender.com/api/health`.
6. To load demo data, open the `pulse-api` shell in Render and run `python manage.py seed_demo`. Set `DEMO_MODE=true` in the `pulse-shared` group first if you want the demo controls; leave it `false` for real users.
7. Create an admin: `python manage.py createsuperuser` in the same shell.

If your service name differs from `pulse-api`, the URL changes too; use yours below.

## 2. Frontend on Vercel

1. In `frontend/vercel.json`, set the `/api/:path*` rewrite destination to your Render URL.
2. In Vercel, **Add New > Project**, import the repo and set **Root Directory** to `frontend`. Vercel detects Vite.
3. Environment variables: `VITE_DEMO_MODE=true` only if the backend has `DEMO_MODE=true`. Leave `VITE_API_URL` empty: the rewrite sends `/api` to Render, so the refresh cookie stays first-party.
4. Deploy, then put the Vercel URL into `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL` on Render and redeploy the backend.

Django admin is served by the backend: `https://pulse-api.onrender.com/admin/`.

## Choices you can change

- **Celery Beat instead of the cron job.** Delete the `pulse-periodic` service, set `USE_CELERY_BEAT=true`, and change the worker command to `celery -A config worker --beat --loglevel=info`.
- **No worker at all.** Delete `pulse-worker` and `pulse-kv` and remove `REDIS_URL`. Jobs then run inside web requests, which is slower for first schedule generation but works.
- **An external scheduler.** Set `CRON_TOKEN` and have it `POST /api/cron` with header `X-Cron-Token: <token>` every 10 minutes.
- **API on its own domain without the Vercel rewrite.** Set `VITE_API_URL` to the API URL and `REFRESH_COOKIE_SAMESITE=None` on the backend.

## Phones: install and push

Vercel serves the frontend over HTTPS, which is all a phone needs to install Leon from its address (Chrome: Install app; Safari: Share > Add to Home Screen) and receive push. Make sure `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT` are set on the Render web and worker services, and that `FRONTEND_URL` is the Vercel address (reminder emails and notification links use it). `frontend/vercel.json` keeps `/sw.js`, `/manifest.webmanifest` and `/icons/` out of the single-page rewrite and serves the manifest with its own content type.

## Production checklist

- `DJANGO_SETTINGS_MODULE=config.settings.prod` (set by the Blueprint). The app refuses to start with a weak secret key.
- `ALLOWED_HOSTS` covers your domain (`.onrender.com` by default; add a custom domain if you use one).
- `python manage.py check --deploy` passes in the Render shell.
- `DEMO_MODE=false` for real students.
