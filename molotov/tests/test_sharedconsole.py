import unittest
import asyncio
import sys
import re

from molotov.sharedconsole import SharedConsole
from molotov.tests.support import dedicatedloop, catch_output


OUTPUT = """\
one
two
3
TypeError\("unsupported operand type(.*)?
TypeError\("unsupported operand type.*"""


class TestSharedConsole(unittest.TestCase):

    @dedicatedloop
    def test_simple_usage(self):
        test_loop = asyncio.get_event_loop()
        console = SharedConsole(interval=0.)

        async def add_lines():
            console.print("one")
            console.print("two")
            console.print("3")
            try:
                1 + 'e'
            except Exception as e:
                console.print_error(e)
                console.print_error(e, sys.exc_info()[2])
            await asyncio.sleep(.2)
            await console.stop()

        with catch_output() as (stdout, stderr):
            adder = asyncio.ensure_future(add_lines())
            displayer = asyncio.ensure_future(console.display())
            test_loop.run_until_complete(asyncio.gather(adder, displayer))

        output = stdout.read()
        test_loop.close()
        self.assertTrue(re.match(OUTPUT, output, re.S | re.M) is not None,
                        output)
