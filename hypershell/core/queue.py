# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Queue server/client implementation."""


# type annotations
from __future__ import annotations
from typing import Tuple, Callable

# standard libs
from multiprocessing.managers import BaseManager
from multiprocessing import JoinableQueue


# default connection details
DEFAULT_BIND = 'localhost'
DEFAULT_PORT = 50001
DEFAULT_AUTH = b'--BADKEY--'
DEFAULT_SIZE = 1  # arbitrary for now
SENTINEL = None


class QueueServer(BaseManager):
    """Server for managing queue."""

    scheduled: JoinableQueue
    completed: JoinableQueue
    connected: JoinableQueue

    def __init__(self, address: Tuple[str, int] = (DEFAULT_BIND, DEFAULT_PORT),
                 authkey: bytes = DEFAULT_AUTH, maxsize: int = DEFAULT_SIZE) -> None:
        """Initialize queue manager."""
        super().__init__(address=address, authkey=authkey)
        self.scheduled = JoinableQueue(maxsize=maxsize)
        self.completed = JoinableQueue(maxsize=maxsize)
        self.connected = JoinableQueue(maxsize=0)  # Note: platform specific max (unbounded in practice)
        self.register('_get_scheduled', callable=self._get_scheduled)
        self.register('_get_completed', callable=self._get_completed)
        self.register('_get_connected', callable=self._get_connected)

    def _get_scheduled(self) -> JoinableQueue:
        return self.scheduled

    def _get_completed(self) -> JoinableQueue:
        return self.completed

    def _get_connected(self) -> JoinableQueue:
        return self.connected

    def __enter__(self) -> QueueServer:
        """Start the server."""
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        """Shutdown the server."""
        self.shutdown()


class QueueClient(BaseManager):
    """Client connection to queue manager."""

    scheduled: JoinableQueue = None
    completed: JoinableQueue = None
    connected: JoinableQueue = None

    _get_scheduled: Callable[[], JoinableQueue]
    _get_completed: Callable[[], JoinableQueue]
    _get_connected: Callable[[], JoinableQueue]

    def __init__(self, address: Tuple[str, int] = (DEFAULT_BIND, DEFAULT_PORT),
                 authkey: bytes = DEFAULT_AUTH) -> None:
        """Initialize queue manager."""
        super().__init__(address=address, authkey=authkey)
        self.register('_get_scheduled')
        self.register('_get_completed')
        self.register('_get_connected')

    def connect(self) -> None:
        """Connect to server."""
        super().connect()
        self.scheduled = self._get_scheduled()
        self.completed = self._get_completed()
        self.connected = self._get_connected()

    def __enter__(self) -> QueueClient:
        """Connect to server."""
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        """Disconnect from server."""
