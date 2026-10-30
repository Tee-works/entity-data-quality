.PHONY: install download run test lint

install:
	pip install -e ".[dev]"

download:        ## latest golden copy from GLEIF, about 570 MB
	edq download

run:
	edq run

test:
	pytest -q

lint:
	ruff check . && ruff format --check . && sqlfluff lint controls
