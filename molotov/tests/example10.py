"""

This Molotov script runs against a GRPC endpoint

"""
from molotov import scenario
from molotov.tests._grpc import helloworld_pb2, helloworld_pb2_grpc


@scenario(weight=40)
async def grpc_scenario(
    session, session_factory="grpc", grpc_url="ipv4:///127.0.0.1:50051"
):
    stub = helloworld_pb2_grpc.GreeterStub(session)
    response = stub.SayHello(helloworld_pb2.HelloRequest(name="Alice"))
    assert response.message == "Hello, Alice!", response.message
