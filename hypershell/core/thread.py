# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Thread base class implementation."""


# type annotations
from __future__ import annotations

# standard libs
import threading

# public interface
__all__ = ['Thread', ]


class Thread(threading.Thread):
    """Threading core behavior."""

    __should_halt: bool = False
    lock: threading.Lock

    def __init__(self, name: str) -> None:
        super().__init__(name=name, daemon=True)
        self.lock = threading.Lock()

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
