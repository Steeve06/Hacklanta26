.PHONY: up down demo test lint api-types

up:
	docker compose up --build

down:
	docker compose down

demo:
	docker compose exec web python manage.py migrate --noinput
	docker compose exec web python manage.py seed_demo

test:
	docker compose exec web pytest
	cd frontend && npm test

lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint && npm run typecheck && npm run format:check

api-types:
	cd backend && python manage.py spectacular --file openapi.json --format openapi-json
	cd frontend && npm run gen:api
