import socket
from requests.packages.urllib3.util import connection as urllib3_conn


_GLOBAL_DEFAULT_TIMEOUT = object()
_cached = {}


def create_connection(address, timeout=_GLOBAL_DEFAULT_TIMEOUT,
                      source_address=None, socket_options=None):
    host, port = address
    err = None
    if address in _cached:
        addrinfo = [_cached[address]]
    else:
        addrinfo = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)

    for res in addrinfo:
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            if socket_options:
                urllib3_conn._set_socket_options(sock, socket_options)

            if timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sa)
            # success, let's use this next time
            _cached[address] = res
            return sock
        except socket.error as _:
            err = _
            if sock is not None:
                sock.close()

    if err is not None:
        raise err
    else:
        raise socket.error("getaddrinfo returns an empty list")


socket.create_connection = create_connection
urllib3_conn.create_connection = create_connection
