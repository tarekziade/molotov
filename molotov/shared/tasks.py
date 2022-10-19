import os
import asyncio
from collections import defaultdict
from collections.abc import MutableSequence
from contextlib import suppress

from molotov.util import cancellable_sleep


class Tasks(MutableSequence):
    """Manages tasks lifecycles across processes."""

    def __init__(self):
        self._tasks = defaultdict(list)

    def _get_tasks(self):
        return self._tasks[os.getpid()]

    def __len__(self):
        return len(self._get_tasks())

    def __getitem__(self, i):
        return self._get_tasks()[i]

    def __delitem__(self, i):
        del self._get_tasks()[i]

    def __setitem__(self, i, v):
        self._get_tasks()[i] = v

    def insert(self, i, v):
        return self._get_tasks().insert(i, v)

    def __str__(self):
        return str(self._get_tasks())

    def ensure_future(self, coro):
        fut = asyncio.ensure_future(coro)
        self.append(fut)
        return fut

    async def gather(self):
        return await asyncio.gather(*self._get_tasks())

    async def cancel_all(self):
        cancellable_sleep.cancel_all()
        for task in reversed(self._get_tasks()):
            if not task.done():
                with suppress(asyncio.CancelledError):
                    task.cancel()
                    await task
        for task in self._get_tasks():
            del task
        self.reset_tasks()

    def reset_tasks(self):
        self._tasks[os.getpid()][:] = []
