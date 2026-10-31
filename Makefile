.PHONY: install lint test validate check

install:
	python3 -m pip install -r requirements-dev.txt

lint:
	python3 -m ruff check .

test:
	python3 -m pytest

validate:
	claude plugin validate .

check: lint test
