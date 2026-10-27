PYTHON ?= python3

.PHONY: run test

run:
	$(PYTHON) main.py

test:
	$(PYTHON) -m unittest discover -s tests -v
