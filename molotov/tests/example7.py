"""

This Molotov script uses events to display concurrency info

"""
import molotov
import time


concurs = []  # [(timestamp, worker count)]


def _now():
    return time.time() * 1000


@molotov.events()
async def record_time(event, **info):
    if event == "current_workers":
        concurs.append((_now(), info["workers"]))


@molotov.global_teardown()
def display_average():
    print("\nconcurrencies: %s", concurs)
    delta = max(ts for ts, _ in concurs) - min(ts for ts, _ in concurs)
    average = sum(value for _, value in concurs) * 1000 / delta
    print("\nAverage concurrency: %.2f VU/s" % average)
