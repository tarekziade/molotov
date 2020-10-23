HERE = $(shell pwd)
PYTHON = python3
TESTNAME = smoke
BIN = $(HERE)/venv/bin
VENV_PIP = $(BIN)/pip3
VENV_PYTHON = $(BIN)/python
INSTALL = $(VENV_PIP) install

.PHONY: build install test


$(VENV_PYTHON):
	$(PYTHON) -m venv venv

build: $(VENV_PYTHON)
	$(INSTALL) --upgrade git+https://github.com/loads/molotov.git

test: build
	$(BIN)/molotov --config molotov.json $(TESTNAME)
