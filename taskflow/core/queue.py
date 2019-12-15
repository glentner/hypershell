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

# standard libs
from abc import ABC as AbstractBase, abstractmethod
from multiprocessing.managers import BaseManager
from multiprocessing import JoinableQueue
from typing import Tuple


# default connection details
ADDRESS  = 'localhost', 50001
AUTHKEY  = b'--BADKEY--'
MAXSIZE  = 10000  # arbitrary for now
SENTINEL = None


class QueueServer(BaseManager):
    """Server for managing queue."""

    tasks: JoinableQueue
    failed: JoinableQueue
    connected: JoinableQueue
    disconnected: JoinableQueue

    def __init__(self, address: Tuple[str, int] = ADDRESS, authkey: bytes = AUTHKEY) -> None:
        """Initialize manager."""
        super().__init__(address=address, authkey=authkey)
        self.tasks = JoinableQueue(maxsize=MAXSIZE)
        self.failed = JoinableQueue(maxsize=MAXSIZE)
        self.connected = JoinableQueue(maxsize=MAXSIZE)
        self.disconnected = JoinableQueue(maxsize=MAXSIZE)
        self.register('_get_tasks', callable=lambda:self.tasks)
        self.register('_get_failed', callable=lambda:self.failed)
        self.register('_get_connected', callable=lambda:self.connected)
        self.register('_get_disconnected', callable=lambda:self.disconnected)

    def __enter__(self) -> 'QueueServer':
        """Start the server."""
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        """Shutdown the server."""
        self.shutdown()


class QueueClient(BaseManager):
    """Client connection to queue manager."""

    tasks: JoinableQueue = None
    failed: JoinableQueue = None
    connected: JoinableQueue = None
    disconnected: JoinableQueue = None

    def __init__(self, address: Tuple[str, int] = ADDRESS, authkey: bytes = AUTHKEY) -> None:
        """Initialize manager."""
        super().__init__(address=address, authkey=authkey)
        self.register('_get_tasks')
        self.register('_get_failed')
        self.register('_get_connected')
        self.register('_get_disconnected')

    def __enter__(self) -> 'QueueClient':
        """Connect to the server."""
        self.connect()
        self.tasks = self._get_tasks()  # pylint: disable=no-member
        self.failed = self._get_failed()  # pylint: disable=no-member
        self.connected = self._get_connected()  # pylint: disable=no-member
        self.disconnected = self._get_disconnected()  # pylint: disable=no-member
        return self

    def __exit__(self, *exc) -> None:
        """Disconnect from the server."""
