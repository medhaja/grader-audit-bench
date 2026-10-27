.PHONY: demo install generate audit test test-unit test-integration

demo:
	python -m audit.serve

install:
	pip install -r requirements.txt

generate:
	python -m audit.generate

audit:
	python -m audit.runner

test:
	python -m pytest -q

test-unit:
	python -m pytest -q -m unit

test-integration:
	python -m pytest -q -m integration
