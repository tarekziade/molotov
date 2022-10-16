from molotov.listeners import BaseListener, EventSender
from molotov.tests.support import TestLoop, async_test, patch_errors


class MyBuggyListener(BaseListener):
    def on_my_event(self, **options):
        raise Exception("Bam")


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
        self.assertTrue(listener.fired)
        self.assertEqual(listener.value, 42)

    @patch_errors
    @async_test
    async def test_buggy_listener(self, console_print, loop, console, results):
        listener = MyBuggyListener()
        eventer = EventSender(console)
        eventer.add_listener(listener)
        await eventer.send_event("my_event")

        self.assertTrue("Bam" in console_print())
