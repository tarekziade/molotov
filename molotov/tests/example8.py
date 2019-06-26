"""

This Molotov script uses events to generate a success/failure output

"""
import json
import molotov
import time

_T = {}


def _now():
    return time.time() * 1000


@molotov.events()
async def record_time(event, **info):
    if event == "scenario_start":
        scenario = info["scenario"]
        index = (info["wid"], scenario["name"])
        _T[index] = _now()
    if event == "scenario_success":
        scenario = info["scenario"]
        index = (info["wid"], scenario["name"])
        start_time = _T.pop(index, None)
        duration = int(_now() - start_time)
        if start_time is not None:
            print(
                json.dumps(
                    {
                        "ts": time.time(),
                        "type": "scenario_success",
                        "name": scenario["name"],
                        "duration": duration,
                    }
                )
            )
    elif event == "scenario_failure":
        scenario = info["scenario"]
        exception = info["exception"]
        index = (info["wid"], scenario["name"])
        start_time = _T.pop(index, None)
        duration = int(_now() - start_time)
        if start_time is not None:
            print(
                json.dumps(
                    {
                        "ts": time.time(),
                        "type": "scenario_failure",
                        "name": scenario["name"],
                        "exception": exception.__class__.__name__,
                        "errorMessage": str(exception),
                        "duration": duration,
                    }
                )
            )
