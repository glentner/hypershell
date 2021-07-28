# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Instrumentation for building finite state machines."""


# type annotations
from __future__ import annotations
from typing import Dict, Callable, Type

# standard libs
from enum import Enum
from abc import ABC

# public interface
__all__ = ['State', 'StateMachine', ]


class State(Enum):
    """Shared base for finite state enums."""


class StateMachine(ABC):
    """Base class for a finite state machine implementation."""

    state: State
    states: Type[State]
    actions: Dict[State, Callable[[], State]]

    __should_halt: bool = False

    def next(self) -> State:
        """Return next state (halt if necessary)."""
        return self.states.HALT if self.__should_halt else self.actions.get(self.state)()

    def run(self) -> None:
        """Run machine until state is set to `HALT`."""
        while self.state is not self.states.HALT:
            self.state = self.next()

    def halt(self) -> None:
        """Set flag to signal for termination."""
        self.__should_halt = True
