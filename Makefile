.PHONY: install run test coverage format lint typecheck check

install:
	python -m pip install -e '.[dev]'

run:
	uvicorn meta_api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

coverage:
	rm -rf coverage_html coverage.xml .coverage
	coverage run -m pytest
	coverage report -m --fail-under=85
	coverage xml -o coverage.xml
	coverage html -d coverage_html

format:
	ruff format .

lint:
	ruff check .

typecheck:
	mypy src

check: format lint typecheck test
