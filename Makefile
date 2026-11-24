.PHONY: setup data test cov clean

setup:
	uv sync

data:
	uv run python -m dk_sales.pipeline

test:
	uv run pytest

cov:
	uv run pytest --cov --cov-report=term --cov-report=html:coverage/html

clean:
	rm -rf data/processed/* coverage .pytest_cache .coverage

.PHONY: lint docker-build ops-secrets ops-up ops-down ops-ps ops-telegram-alerts grafana

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy

docker-build:
	docker build -t dua-kelinci-sales:local .

ops-secrets:
	./scripts/gen-secrets.sh

grafana:
	uv run python scripts/build_grafana.py

ops-up:
	docker compose --profile ops up -d --build

ops-down:
	docker compose --profile ops down

ops-ps:
	docker compose --profile ops ps

# Writes the Telegram contact point for Grafana alerts from TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.
ops-telegram-alerts:
	./scripts/grafana-telegram.sh
