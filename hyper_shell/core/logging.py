# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""
Logging configuration.

hyper-shell uses the `logalpha` package for logging functionality. All messages
are written to <stderr> and should be redirected by their parent processes.
"""

# standard libraries
import io
import sys
import socket
from datetime import datetime
from dataclasses import dataclass

# external libraries
from logalpha import levels, colors, messages, handlers, loggers
from cmdkit import logging as _cmdkit_logging

# internal library
from ..__meta__ import __appname__

# type annotations
from typing import Callable


LEVELS = levels.Level.from_names(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
COLORS = colors.Color.from_names(['blue', 'green', 'yellow', 'red', 'magenta'])
RESET = colors.Color.reset
HOST = socket.gethostname()


@dataclass
class Message(messages.Message):
    """A `logalpha.messages.Message` with a timestamp:`datetime` and source:`str`."""
    timestamp: datetime
    source: str


class Logger(loggers.Logger):
    """Logger for hyper-shell."""

    Message: type = Message
    callbacks: dict = {'timestamp': datetime.now,
                       'source': (lambda: __appname__)}

    def with_name(self, name: str) -> 'Logger':
        """Inject alternate `name` into callbacks."""
        logger = self.__class__()
        logger.callbacks = {**logger.callbacks, 'source': (lambda: name)}
        logger.handlers = self.handlers[:]  # same handler instances
        return logger

    debug: Callable[[str], None]
    info: Callable[[str], None]
    warning: Callable[[str], None]
    error: Callable[[str], None]
    critical: Callable[[str], None]


@dataclass
class ConsoleHandler(handlers.Handler):
    """Write messages to <stderr>."""

    level: levels.Level
    resource: io.TextIOWrapper = sys.stderr

    def format(self, msg: Message) -> str:
        """Syslog style with padded spaces."""
        timestamp = msg.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        return f'{timestamp} {HOST} {msg.level.name:<8} {msg.source}: {msg.content}'


@dataclass
class SimpleConsoleHandler(handlers.Handler):
    """Write shorter messages to <stderr> with color."""

    level: levels.Level
    resource: io.TextIOWrapper = sys.stderr

    def format(self, msg: Message) -> str:
        """Colorize the log level and with only the message."""
        COLOR = Logger.colors[msg.level.value].foreground
        return f'{COLOR}{msg.source}: {msg.content}{RESET}'


DETAILED_HANDLER = ConsoleHandler(LEVELS[2])
SIMPLE_HANDLER = SimpleConsoleHandler(LEVELS[2])

logger = Logger()
logger.handlers.append(SIMPLE_HANDLER)

# inject logger back into cmdkit library
_cmdkit_logging.log = logger


def setup(logger: Logger, debug: bool = False, verbose: bool = False, logging: bool = False):
    """
    Setup process used by command-line interface.
    Also required to repeat setup for forked process.
    """
    if logging:
        logger.handlers[0] = DETAILED_HANDLER
    if debug:
        logger.handlers[0].level = logger.levels[0]
    elif verbose:
        logger.handlers[0].level = logger.levels[1]
    else:
        logger.handlers[0].level = logger.levels[2]
