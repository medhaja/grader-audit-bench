.PHONY: demo install generate audit test test-unit test-integration kt-video kt-video-capture

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

# KT video (docs/kt-video/README.md). Rebuilds audio and MP4 from the approved script and the frozen
# snapshot/captures; it never reruns the audit. Use KT_PY=.venv/bin/python on macOS/Linux.
KT_PY ?= .venv/Scripts/python

kt-video:
	cd docs/kt-video && $(KT_PY) tts.py && node render.mjs

# Explicit, separate step: re-capture UI screenshots from a running mock-mode app
# (env -u JUDGE_MODEL python -m audit.serve). Aborts if the app's results differ from the snapshot.
kt-video-capture:
	cd docs/kt-video && node capture.mjs
