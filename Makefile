.PHONY: install data build analysis test lint app all

install:            ## install package + dev tools
	pip install -e ".[dev]"

data:               ## download raw open data (~250 MB) into data/raw
	python -m cypmh_access.download

build:              ## DuckDB warehouse: staging -> marts, export parquet + boundaries
	python -m cypmh_access.build

analysis:           ## statistics, figures and reports/results.json
	python -m cypmh_access.analysis

test:               ## unit tests, data contracts, dashboard smoke test
	pytest -q

lint:
	ruff check src app tests

app:                ## launch the interactive dashboard
	streamlit run app/streamlit_app.py

all: data build analysis test
