from grpc import aio

from molotov.api import session_factory


@session_factory("grpc")
def grpc_session(loop, console, verbose, statsd, trace_config, **kw):
    url = kw["grpc_url"]
    channel = aio.insecure_channel(url)
    channel._trace_configs = [trace_config]  # type: ignore

    def _print(data):
        if console is None:
            print(data)
        else:
            console.print(data)

    channel.print = _print  # type: ignore
    return channel
