"""

This Molotov script show how you can print
the average response time.

"""
import molotov
import time


_T = {}


def _now():
    return time.time() * 1000


@molotov.events()
async def record_time(event, **info):
    req = info.get("request")
    if event == "sending_request":
        _T[req] = _now()
    elif event == "response_received":
        _T[req] = _now() - _T[req]


@molotov.global_teardown()
def display_average():
    average = sum(_T.values()) / len(_T)
    print("\nAverage response time %dms" % average)
