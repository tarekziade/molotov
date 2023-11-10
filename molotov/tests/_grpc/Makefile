PYTHON ?= python

.PHONY: proto


install:
	$(PYTHON) -m pip install grpcio-tools

proto:
	$(PYTHON) -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. helloworld.proto

run:
	$(PYTHON) service.py

