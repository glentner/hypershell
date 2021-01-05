# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Implementation of a finite state machine for the `SubmitThread`."""


# type annotations
from __future__ import annotations
from typing import List, Iterable, Iterator, Type

# standard libs
from abc import ABC, abstractmethod
import logging

# internal libs
from hypershell.database.model import Task


# module level logger
log = logging.getLogger(__name__)


# global default for number of tasks to buffer for flushing
DEFAULT_BUFFERSIZE = 10


def submit_tasks(buffer: List[Task]) -> None:
    """
    Submit existing `buffer`ed tasks to the database.

    Note:
        This will clear the buffer.
    """
    Task.add_all(buffer)
    log.debug(f'Added {len(buffer)} tasks')
    buffer.clear()


class State(ABC):
    """
    One of a finite number of machine states.

    Each state defines some action to take within the context of the existing machine.
    Each state returns the next State upon completing its action.
    The machine will step through states until the Halt(State) is reached.
    """

    @abstractmethod
    def run(self, machine: Machine) -> State:
        """Run some action and return next state."""

    def next(self, machine: Machine) -> State:
        """Return next state (Halt() if `machine` is not running)."""
        return Halt() if not machine.is_running else self.run(machine)


class Start(State):
    def run(self, machine: Machine) -> State:
        """Initial State, simply returns the first 'real' state."""
        return Buffering()


class Buffering(State):
    def run(self, machine: Machine) -> State:
        """Get the next task line and buffer it."""
        try:
            args = str(next(machine.data)).strip()
            task = Task.new(args)
            machine.buffer.append(task)
            machine.count += 1
            log.debug(f'Buffered task ({args})')
        except StopIteration:
            machine.is_running = False
            return Finalize()
        else:
            return CheckBuffer()


class CheckBuffer(State):
    def run(self, machine: Machine) -> State:
        """Returns Flush() if the buffer has reached its maximum size."""
        if len(machine.buffer) >= machine.buffersize:
            return FlushBuffer()
        else:
            return Buffering()


class FlushBuffer(State):
    def run(self, machine: Machine) -> State:
        """Submit buffered tasks to the database."""
        submit_tasks(machine.buffer)
        return Buffering()


class Finalize(State):
    def run(self, machine: Machine) -> State:
        """Same as FlushBuffer(), but returns Halt()."""
        submit_tasks(machine.buffer)
        return Halt()


class Halt(State):
    def run(self, machine: Machine) -> State:
        """The machine should halt."""
        return Halt()  # NOTE: dead code (machine should halt, not continue)


class Machine:
    """
    A finite state machine for buffering and submitting tasks to the database.

    We can break out of the pattern by calling `terminate` on the machine.
    """

    data: Iterator[str]
    is_running: bool
    state: State

    count: int
    buffer: List[Task]
    buffersize: int

    def __init__(self, source: Iterable[str], buffersize: int = 1) -> None:
        """Initialize machine state."""
        self.data = iter(source)
        self.is_running = True
        self.state = Start()
        self.count = 0
        self.buffer = list()
        self.buffersize = buffersize

    def run(self) -> None:
        """Run machine."""
        while True:
            self.state = self.state.next(self)
            if isinstance(self.state, Halt):
                break

    def terminate(self) -> None:
        self.is_running = False
