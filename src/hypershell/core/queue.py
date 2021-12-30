# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Queue server/client implementation."""


# type annotations
from __future__ import annotations
from typing import Dict, List, Callable, Union, Optional, Any, Iterable

# standard libs
from multiprocessing.managers import BaseManager
from multiprocessing import JoinableQueue
from abc import ABC, abstractmethod
from dataclasses import dataclass

# internal libs
from hypershell.core.config import default, config as _config

# public interface
__all__ = ['QueueConfig', 'QueueInterface', 'QueueServer', 'QueueClient']


@dataclass
class QueueConfig:
    """Connection details for queue interface."""

    host: str = default.server.bind
    port: int = default.server.port
    auth: str = default.server.auth
    size: int = default.server.queuesize

    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, int]]) -> QueueConfig:
        """Load config from existing dictionary values."""
        return cls(**data)

    @classmethod
    def load(cls) -> QueueConfig:
        """Initialize from global configuration."""
        return cls.from_dict({
            'host': _config.server.host,
            'port': _config.server.port,
            'auth': _config.server.auth,
            'size': _config.server.queuesize,
        })


class QueueInterface(BaseManager, ABC):
    """The queue interface provides access to three managed distributed queues."""

    config: QueueConfig
    scheduled: JoinableQueue[Optional[List[bytes]]]
    completed: JoinableQueue[Optional[List[bytes]]]
    heartbeat: JoinableQueue[Optional[bytes]]

    def __init__(self, config: QueueConfig) -> None:
        """Initialize queue interface."""
        self.config = config
        super().__init__(address=(self.config.host, self.config.port), authkey=self.config.auth.encode())

    @classmethod
    def new(cls) -> QueueInterface:
        """Create new interface from global configuration."""
        return cls(config=QueueConfig.load())

    @abstractmethod
    def __enter__(self) -> QueueInterface:
        """Start server or connect from client."""

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop or disconnect."""


class QueueServer(QueueInterface):
    """Server for managing queue."""

    def start(self, initializer: Optional[Callable[..., Any]] = ..., initargs: Iterable[Any] = ...) -> None:
        """Initialize queues and start server."""
        self.scheduled = JoinableQueue(maxsize=self.config.size)
        self.completed = JoinableQueue(maxsize=self.config.size)
        self.heartbeat = JoinableQueue(maxsize=0)
        self.register('_get_scheduled', callable=self._get_scheduled)
        self.register('_get_completed', callable=self._get_completed)
        self.register('_get_heartbeat', callable=self._get_heartbeat)
        super().start()

    def _get_scheduled(self) -> JoinableQueue[Optional[List[bytes]]]:
        return self.scheduled

    def _get_completed(self) -> JoinableQueue[Optional[List[bytes]]]:
        return self.completed

    def _get_heartbeat(self) -> JoinableQueue[Optional[bytes]]:
        return self.heartbeat

    def __enter__(self) -> QueueServer:
        """Start the server."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Shutdown the server."""
        self.shutdown()


class QueueClient(QueueInterface):
    """Client connection to queue manager."""

    _get_scheduled: Callable[[], JoinableQueue[Optional[List[bytes]]]]
    _get_completed: Callable[[], JoinableQueue[Optional[List[bytes]]]]
    _get_heartbeat: Callable[[], JoinableQueue[Optional[bytes]]]

    def connect(self) -> None:
        """Connect to server."""
        self.register('_get_scheduled')
        self.register('_get_completed')
        self.register('_get_heartbeat')
        super().connect()
        self.scheduled = self._get_scheduled()
        self.completed = self._get_completed()
        self.heartbeat = self._get_heartbeat()

    def __enter__(self) -> QueueClient:
        """Connect to server."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Disconnect from server."""
