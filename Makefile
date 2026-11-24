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
