"""

This Molotov script uses events to generate a success/failure output

"""
import molotov
import time


@molotov.events()
async def print_test_case(event, **info):
    if event == 'scenario_success':
        scenario = info['scenario']
        print({
            "ts": time.time(),
            "type": "scenario_success",
            "name": scenario['name'],
        })
    elif event == 'scenario_failure':
        scenario = info['scenario']
        exception = info['exception']
        print({
            "ts": time.time(),
            "type": "scenario_failure",
            "name": scenario['name'],
            "exception": exception.__class__.__name__,
            "errorMessage": str(exception),
        })
