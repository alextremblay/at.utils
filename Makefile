SHELL := /bin/bash

help: ## Show this help.
@fgrep -h "##"  | fgrep -v fgrep | sed -e 's/\26394//' | sed -e 's/##//'

test: ## Run all the tests
	poetry run py.test

install: ## Install this package to the system site packages
	rm -f dict/*
	poetry build
	sudo pip install dist/*.whl
