.PHONY: typehint
typehint:
	mypy --ignore-missing-imports python/
.PHONY: lint
lint:
	pylint python/
.PHONY: checklist
checklist: lint typehint
.PHONY: isort
isort:
	isort python/
.PHONY: format
format:
	black -l 120 python/
.PHONY: clean
clean:
	find . -type f -name "*.pyc" | xargs rm -fr
	find . -type d -name __pycache__ | xargs rm -fr
	find . -type d -name .mypy_cache | xargs rm -fr