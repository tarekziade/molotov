import subprocess
import time
from concurrent import futures
import sys

import grpc
from molotov.tests._grpc import helloworld_pb2
from molotov.tests._grpc import helloworld_pb2_grpc


class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        response = helloworld_pb2.HelloReply()
        response.message = f"Hello, {request.name}!"
        return response


def run_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("Server started. Listening on 0.0.0.0:50051")
    server.wait_for_termination()


class GRPCServer:
    def __init__(self):
        self.p = subprocess.Popen([sys.executable, "service.py"])
        timer.sleep(1)

    def stop(self):
        self.p.terminate()


if __name__ == "__main__":
    run_server()
