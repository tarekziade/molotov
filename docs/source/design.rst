Design
======

**molotov** creates an :class:`aiohttp.ClientSession` instance, then
uses asyncio's event loop to run concurrent coroutines that call
every function that are decorated with the :func:`scenario` decorator.

Each coroutine picks a function randomly, using the weight defined
in the decorator, and executes it. It repeats this cycle until
the test is over.

**molotov** can also spwan several processes and do what
was previously described in each one of them.
