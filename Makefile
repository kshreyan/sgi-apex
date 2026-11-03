PY ?= python
.PHONY: setup test lint ingest validate forecast backtest chairman-brief all site serve simulate optimize board-pack

setup:          ## install package + dev tools
	$(PY) -m pip install -e '.[dev]'
test:
	$(PY) -m pytest -q
lint:
	$(PY) -m ruff check src tests
validate:       ## entity registry + reconciliation gate
	sgi registry
ingest:
	sgi ingest
all forecast backtest site:  ## full milestone-1 loop -> artifacts + site/data
	sgi run
chairman-brief:
	sgi chairman-brief
serve:
	cd site && $(PY) -m http.server 8000
simulate optimize board-pack:
	@echo "'$@' is planned for a later milestone (see docs/build_plan_90_day.md)"; exit 1
