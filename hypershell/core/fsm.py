# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Instrumentation for building finite state machines."""


# type annotations
from __future__ import annotations

# standard libs
from abc import ABC, abstractmethod

# public interface
__all__ = ['State', 'StateMachine', 'HALT', ]


class State(ABC):
    """
    One of a finite number of machine states.

    Each state defines some action to take within the context of the existing machine.
    Each state returns the next State upon completing its action.
    The machine will step through states until the Halt(State) is reached.
    """

    @abstractmethod
    def run(self, machine: StateMachine) -> State:
        """Run some action and return next state."""

    def next(self, machine: StateMachine) -> State:
        """Return next state (`HALT` if `machine` is not running)."""
        return HALT if not machine.is_running else self.run(machine)


class Halt(State):
    def run(self, machine: StateMachine) -> State:
        """The machine should halt."""
        machine.halt()
        return HALT  # Note: dead code (the machine should halt).


HALT = Halt()


class StateMachine(ABC):
    """
    Base class for a finite state machine implementation.

    The :meth:`run` method invokes the :meth:`State.next` method
    until Halt() is returned.
    """

    __state: State
    __should_halt: bool = False

    def __init__(self, start: State) -> None:
        """Should initialize starting state."""
        self.__state = start

    def run(self) -> None:
        """Run machine until state is set to `Halt`."""
        while not isinstance(self.__state, Halt):
            self.__state = self.__state.next(self)

    @property
    def is_running(self) -> bool:
        return not self.__should_halt

    def halt(self) -> None:
        """
        Set flag to signal for termination.

        Normally, the `run` method will simply run until completion. When :meth:`StateMachine.run`
        is invoked from inside a `Thread` however, the `halt` method can be used to signal
        a request to halt early.
        """
        self.__should_halt = True
