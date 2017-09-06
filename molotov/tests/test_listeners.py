from molotov.listeners import BaseListener, EventSender
from molotov.tests.support import TestLoop, async_test, serialize


class TestListeners(TestLoop):
    @async_test
    async def test_add_listener(self, loop, console, results):
        class MyListener(BaseListener):
            def __init__(self):
                self.fired = False
                self.value = None

            def on_my_event(self, **options):
                self.fired = True
                self.value = options["value"]

        listener = MyListener()
        eventer = EventSender(console)
        eventer.add_listener(listener)
        await eventer.send_event("my_event", value=42)
        await serialize(console)

        self.assertTrue(listener.fired)
        self.assertEqual(listener.value, 42)

    @async_test
    async def test_buggy_listener(self, loop, console, results):
        class MyListener(BaseListener):
            def on_my_event(self, **options):
                raise Exception("Bam")

        listener = MyListener()
        eventer = EventSender(console)
        eventer.add_listener(listener)
        await eventer.send_event("my_event")
        resp = await serialize(console)
        self.assertTrue("Bam" in resp)
