.PHONY: install generate build check report audit test all

install:
	python3 -m pip install -r requirements-dev.txt

generate:
	python3 scripts/generate_articles.py --count 1

build:
	python3 scripts/build_site.py

check:
	python3 scripts/quality_check.py --include-site

report:
	python3 scripts/weekly_report.py

audit:
	python3 scripts/launch_audit.py

test:
	python3 -m pytest

all: generate build report check test
