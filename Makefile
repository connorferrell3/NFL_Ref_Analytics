PY := .venv/bin/python
export PYTHONPATH := src

refresh:
	$(PY) -m nfl_refs.ingest
	$(PY) -m nfl_refs.transform

build:
	$(PY) -m nfl_refs.transform

app:
	.venv/bin/streamlit run app/dashboard.py

test:
	$(PY) -m pytest -q

.PHONY: refresh build app test
