mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
CURRENT_DIR := $(patsubst %/,%,$(dir $(mkfile_path)))

format:
	ruff format $(CURRENT_DIR)/simple_bot

lint:
	ruff check $(CURRENT_DIR)/simple_bot