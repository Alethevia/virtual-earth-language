.PHONY: setup run-min test
setup:
	python -m pip install -r requirements.txt
run-min:
	python experiments/minimal_run.py
test:
	python -m pytest -q
