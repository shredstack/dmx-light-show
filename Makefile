PYTHON := python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: deps venv install clean reinstall help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-12s %s\n", $$1, $$2}'

QLC_VERSION := 4.14.3
QLC_DMG := QLC+_$(QLC_VERSION)_$(shell uname -m).dmg
QLC_URL := https://www.qlcplus.org/downloads/$(QLC_VERSION)/$(QLC_DMG)

deps: ## Install system dependencies (QLC+, Python 3.12, FFmpeg)
	@if [ ! -d /Applications/QLC+.app ] || \
	    [ ! -f /Applications/QLC+.app/Contents/MacOS/qlcplus ]; then \
		echo "Installing QLC+ $(QLC_VERSION)..."; \
		curl -L -o /tmp/$(QLC_DMG) "$(QLC_URL)"; \
		hdiutil attach /tmp/$(QLC_DMG) -nobrowse; \
		cp -R "/Volumes/Q Light Controller Plus $(QLC_VERSION)/QLC+.app" /Applications/; \
		hdiutil detach "/Volumes/Q Light Controller Plus $(QLC_VERSION)"; \
		rm -f /tmp/$(QLC_DMG); \
		echo "QLC+ $(QLC_VERSION) installed."; \
	fi
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
