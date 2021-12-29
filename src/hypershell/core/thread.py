# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Thread base class implementation."""


# type annotations
from __future__ import annotations
from typing import Optional

# standard libs
from abc import ABC, abstractmethod
import threading

# public interface
__all__ = ['Thread', ]


class Thread(threading.Thread, ABC):
    """Extends threading.Thread to provide exception handling."""

    exc: Exception = None
    lock: threading.Lock

    __should_halt: bool = False

    def __init__(self, name: str) -> None:
        super().__init__(name=name, daemon=True)
        self.lock = threading.Lock()

    @abstractmethod
    def run_with_exceptions(self) -> None:
        """Implement `run` which may raise exceptions."""

    def run(self) -> None:
        """Call `run_with_exceptions` within a try/except block."""
        try:
            self.run_with_exceptions()
        except Exception as error:
            self.exc = error

    @classmethod
    def new(cls, *args, **kwargs) -> Thread:
        """Initialize and start the thread."""
        thread = cls(*args, **kwargs)
        thread.start()
        return thread

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Signal to terminate."""
        self.__should_halt = True
        if wait:
            self.join(timeout=timeout)

    def join(self, timeout: Optional[float] = None) -> None:
        """Calls Thread.join but re-raises exceptions."""
        super().join(timeout=timeout)
        if self.exc:
            raise self.exc
