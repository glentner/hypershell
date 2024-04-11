# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Instrumentation for building finite state machines."""


# type annotations
from __future__ import annotations
from typing import Dict, Callable, Type

# standard libs
# import time  # NOTE: commented section below
# import random
from enum import Enum
from abc import ABC

# internal libs
from hypershell.core.exceptions import write_traceback
from hypershell.core.logging import Logger

# public interface
__all__ = ['State', 'StateMachine', ]


log = Logger.with_name(__name__)


class State(Enum):
    """Shared base for finite state enums (must have at least HALT)."""


class StateMachine(ABC):
    """Base class for a finite state machine implementation."""

    state: State
    states: Type[State]
    actions: Dict[State, Callable[[], State]]

    __should_halt: bool = False

    def next(self) -> State:
        """Return next state (halt if necessary)."""
        previous_state = self.state
        try:
            if self.__should_halt:
                return self.states.HALT  # noqa: HALT defined in implemented State enums
            else:
                action = self.actions.get(previous_state)
                next_state = action()
        except Exception as error:
            log.critical(f'Uncaught exception from {self.__class__}')
            write_traceback(error, logger=log, module=__name__)
            raise
        else:
            # NOTE: Development aids not typically engaged
            # time.sleep(random.uniform(0, 5))  # FUZZ
            # log.devel(f'{self.__class__.__name__}: {previous_state} -> {next_state}')
            return next_state

    def run(self) -> None:
        """Run machine until state is set to `HALT`."""
        while self.state is not self.states.HALT:  # noqa: HALT defined in implemented State enums
            self.state = self.next()

    def halt(self) -> None:
        """Set flag to signal for termination."""
        self.__should_halt = True
