"""

This Molotov script runs against a GRPC endpoint

"""
import grpc

from molotov import scenario, session_factory
from molotov.tests._grpc import helloworld_pb2, helloworld_pb2_grpc


@session_factory("grpc")
def grpc_session(*args, **kw):
    import pdb

    pdb.set_trace()

    # XXX decorate Channel with motolov specific stuff

    return grpc.insecure_channel("ipv4:///127.0.0.1:8080")


@scenario(weight=40)
async def grpc_scenario(session, session_factory="grpc"):
    import pdb

    pdb.set_trace()

    stub = helloworld_pb2_grpc.GreeterStub(session)
    response = stub.SayHello(helloworld_pb2.HelloRequest(name="Alice"))
    print("Response received: " + response.message)
