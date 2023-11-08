HERE = $(shell pwd)
BIN = $(HERE)/bin
PYTHON = $(BIN)/python
INSTALL = $(BIN)/pip install --no-deps
BUILD_DIRS = bin build include lib lib64 man share
VIRTUALENV = virtualenv

.PHONY: all test build clean docs

all: build

$(PYTHON):
	$(VIRTUALENV) $(VTENV_OPTS) .

build: $(PYTHON)
	$(PYTHON) setup.py develop
	$(BIN)/pip install tox

clean:
	rm -rf $(BUILD_DIRS)

test: build
	$(BIN)/tox

docs:  build
	$(BIN)/tox -e docs

$(BIN)/ruff:
	$(BIN)/pip install ruff

ruff: $(BIN)/ruff
	$(BIN)/ruff check setup.py molotov/
	$(BIN)/ruff format setup.py molotov/*.py

