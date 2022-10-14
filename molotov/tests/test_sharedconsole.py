import unittest
import asyncio
import sys
import os
import re
import multiprocess

from molotov.ui.console import SharedConsole
from molotov.tests.support import dedicatedloop, catch_output


OUTPUT = """\
one
two
3
<style fg="gray">TypeError\\("unsupported operand type(.*)?
<style fg="gray">TypeError\\("unsupported operand type.*"""


# pre-forked variable
_CONSOLE = SharedConsole(interval=0.0)
_PROC = []


def run_worker(input):
    if os.getpid() not in _PROC:
        _PROC.append(os.getpid())
    _CONSOLE.print("hello")
    try:
        3 + ""
    except Exception:
        _CONSOLE.print_error("meh")

    with catch_output() as (stdout, stderr):
        loop = asyncio.new_event_loop()
        fut = asyncio.ensure_future(_CONSOLE.start(), loop=loop)
        loop.run_until_complete(fut)
        loop.close()

    stdout = stdout.read()
    assert stdout == "", stdout


class TestSharedConsole(unittest.TestCase):
    @unittest.skipIf("GITHUB_ACTIONS" in os.environ, "GH action")
    @dedicatedloop
    def test_simple_usage(self):
        test_loop = asyncio.get_event_loop()
        console = SharedConsole(interval=0.0)

        written = []

        def _write(data):
            written.append(data)

        console.terminal.write = _write
        console.errors.write = _write

        async def add_lines():
            console.print("one")
            console.print("two")
            console.print("3")
            try:
                1 + "e"
            except Exception as e:
                console.print_error(e)
                console.print_error(e, sys.exc_info()[2])
            await asyncio.sleep(0.2)
            await console.stop()

        with catch_output() as (stdout, stderr):
            adder = asyncio.ensure_future(add_lines())
            displayer = asyncio.ensure_future(console.start())
            test_loop.run_until_complete(asyncio.gather(adder, displayer))

        test_loop.close()
        output = "".join(written)

        self.assertTrue(re.match(OUTPUT, output, re.S | re.M) is not None, output)

    @unittest.skipIf(os.name == "nt", "win32")
    @unittest.skipIf("GITHUB_ACTIONS" in os.environ, "GH action")
    @dedicatedloop
    def test_multiprocess(self):
        test_loop = asyncio.get_event_loop()

        # now let's try with several processes
        pool = multiprocess.Pool(3)
        try:
            inputs = [1] * 3
            pool.map(run_worker, inputs)
        finally:
            pool.close()

        async def stop():
            await asyncio.sleep(1)
            await _CONSOLE.stop()

        with catch_output() as (stdout, stderr):
            stop = asyncio.ensure_future(stop())
            display = asyncio.ensure_future(_CONSOLE.start())
            test_loop.run_until_complete(asyncio.gather(stop, display))

        output = stdout.read()
        for pid in _PROC:
            self.assertTrue("[%d]" % pid in output)
        test_loop.close()
