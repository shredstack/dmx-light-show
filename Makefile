PYTHON := python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: deps venv install clean reinstall help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-12s %s\n", $$1, $$2}'

deps: ## Install system dependencies (QLC+, Python 3.12, FFmpeg)
	brew install --cask qlc+
	brew install python@3.12
	brew install ffmpeg

venv: $(BIN)/activate ## Create virtual environment

$(BIN)/activate:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip setuptools wheel
	@echo "\nVenv created. Run: source $(VENV)/bin/activate"

install: deps venv ## Full setup: system deps + venv + Python packages
	$(BIN)/pip install --only-binary :all: llvmlite numba
	$(BIN)/pip install -r requirements.txt
	@echo "\nSetup complete. Run: source $(VENV)/bin/activate"

clean: ## Remove virtual environment
	rm -rf $(VENV)
	@echo "Venv removed."

reinstall: clean install ## Remove and recreate everything from scratch
