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
MAXSIZE  = 10_000  # arbitrary for now
SENTINEL = None


class QueueServer(BaseManager):
    """Server for managing queue."""

    tasks: JoinableQueue
    finished: JoinableQueue
    connected: JoinableQueue

    def __init__(self, address: Tuple[str, int] = ADDRESS, authkey: bytes = AUTHKEY,
                 max_tasks: int = MAXSIZE, max_connections: int = MAXSIZE) -> None:
        """Initialize manager."""
        super().__init__(address=address, authkey=authkey)
        self.tasks = JoinableQueue(maxsize=max_tasks)
        self.finished = JoinableQueue(maxsize=max_tasks)
        self.connected = JoinableQueue(maxsize=max_connections)  # FIXME: can this be unbounded?
        self.register('_get_tasks', callable=lambda:self.tasks)
        self.register('_get_finished', callable=lambda:self.finished)
        self.register('_get_connected', callable=lambda:self.connected)

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
    finished: JoinableQueue = None
    connected: JoinableQueue = None

    def __init__(self, address: Tuple[str, int] = ADDRESS, authkey: bytes = AUTHKEY) -> None:
        """Initialize manager."""
        super().__init__(address=address, authkey=authkey)
        self.register('_get_tasks')
        self.register('_get_finished')
        self.register('_get_connected')

    def __enter__(self) -> 'QueueClient':
        """Connect to the server."""
        self.connect()
        self.tasks = self._get_tasks()  # pylint: disable=no-member
        self.finished = self._get_finished()  # pylint: disable=no-member
        self.connected = self._get_connected()  # pylint: disable=no-member
        return self

    def __exit__(self, *exc) -> None:
        """Disconnect from the server."""
