.PHONY: demo install generate audit test

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
