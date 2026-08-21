.PHONY: install run test coverage format lint typecheck check

install:
	python -m pip install -e '.[dev]'

run:
	uvicorn meta_api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

coverage:
	coverage run -m pytest --junitxml=test-results.xml && coverage report --fail-under=80 --show-missing

format:
	ruff format .

lint:
	ruff check .

typecheck:
	mypy src

check: format lint typecheck test
