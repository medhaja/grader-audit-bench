.PHONY: demo install generate audit test test-unit test-integration kt-video

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

# KT video (docs/kt-video/README.md): facts from the repo -> Kokoro voiceover -> rendered MP4.
# Reads results/ and data/; never reruns the audit. Use KT_PY=.venv/bin/python on macOS/Linux.
KT_PY ?= .venv/Scripts/python

kt-video:
	cd docs/kt-video && $(KT_PY) facts.py && $(KT_PY) tts.py && node render.mjs
