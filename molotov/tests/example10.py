"""

This Molotov script runs against a GRPC endpoint

"""
from molotov import scenario, session_factory


@session_factory("grpc")
def grpc_session():
    from aiogrpc import insecure_channel

    return insecure_channel("ipv4:///127.0.0.1:8080")


@scenario(weight=40)
async def grpc_scenario(session, session_factory="grpc"):
    import pdb

    pdb.set_trace()


@scenario(weight=20)
async def http_scenario(session):
    import pdb

    pdb.set_trace()
