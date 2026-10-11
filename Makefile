.PHONY: setup up down demo demo-sample test e2e lint api-types

# Create .env from the example and fill in a secret key and Web Push keys.
setup:
	@test -f .env || cp .env.example .env
	docker compose run --rm --no-deps --user "$$(id -u):$$(id -g)" \
		-v "$(CURDIR)/.env:/tmp/pulse.env" web python manage.py init_env /tmp/pulse.env

up:
	docker compose up --build

down:
	docker compose down

# Reset the demo data and print the demo accounts. Run while `make up` is running.
# Courses start empty until their teachers sign up; demo-sample fills them with the sample term.
demo:
	docker compose exec web python manage.py migrate --noinput
	docker compose exec web python manage.py seed_demo

demo-sample:
	docker compose exec web python manage.py migrate --noinput
	docker compose exec web python manage.py seed_demo --sample-content

test:
	docker compose exec web pytest
	cd frontend && npm test

e2e:
	cd frontend && npx playwright test

lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint && npm run typecheck && npm run format:check

api-types:
	cd backend && python manage.py spectacular --file openapi.json --format openapi-json
	cd frontend && npm run gen:api
