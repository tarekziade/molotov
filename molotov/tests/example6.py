import molotov
import time


_RECORDER = {}


@molotov.events()
async def record_time(event, **info):
    if event == 'sending_request':
        _RECORDER[info['request']] = time.time()
    elif event == 'response_received':
        req = info['request']
        _RECORDER[req] = time.time() - _RECORDER[req]


@molotov.global_teardown()
def display_average():
    total = sum([float(t) for t in _RECORDER.values()])
    average = float(total) / float(len(_RECORDER))
    print("Average response time %.4f" % average)
