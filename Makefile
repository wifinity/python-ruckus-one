# vim:ft=make:noexpandtab:
.PHONY: format format-check lint type-check unit-tests tests help
.DEFAULT_GOAL := help

format: ## Run black formatter
	uv run black .

format-check: ## Check black formatting
	@echo "Running black"
	uv run black --check --diff .

lint: format-check ## Run linter
	@echo "Running flake8"
	uv run flake8 ruckus_one/ --format=github

type-check: ## Run type checks
	@echo "Running mypy"
	uv run mypy ruckus_one --explicit-package-bases --show-error-codes --error-summary

unit-tests: ## Run unit tests
	@echo "Running pytest"
	uv run pytest -v -s tests/

tests: lint type-check unit-tests ## Run all tests
test: tests

venv: ## Create venv
	test -d .venv || uv venv
	uv pip install -r requirements.txt -r requirements-dev.txt

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'