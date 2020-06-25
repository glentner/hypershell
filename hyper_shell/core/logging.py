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

# type annotations
from typing import List, Callable

# standard libraries
import os
import io
import sys
import socket
from datetime import datetime
from dataclasses import dataclass

# external libraries
from logalpha import levels, colors, messages, handlers, loggers
from cmdkit.app import Application, exit_status

# internal library
from ..__meta__ import __appname__


LEVELS = levels.Level.from_names(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
COLORS = colors.Color.from_names(['blue', 'green', 'yellow', 'red', 'magenta'])
RESET = colors.Color.reset
HOST = socket.gethostname()


# named logging levels
DEBUG    = LEVELS[0]
INFO     = LEVELS[1]
WARNING  = LEVELS[2]
ERROR    = LEVELS[3]
CRITICAL = LEVELS[4]

LEVELS_BY_NAME = {'DEBUG': DEBUG, 'INFO': INFO, 'WARNING': WARNING,
                  'ERROR': ERROR, 'CRITICAL': CRITICAL}


# NOTE: global handler list lets `Logger` instances aware of changes
#       to other logger's handlers. (i.e., changing from StandardHandler to DetailedHandler).
_handlers: List[handlers.Handler] = []


@dataclass
class Message(messages.Message):
    """A `logalpha.messages.Message` with a timestamp:`datetime` and source:`str`."""
    timestamp: datetime
    source: str


class Logger(loggers.Logger):
    """Logger for hyper-shell."""

    source: str = __appname__
    Message: type = Message
    callbacks: dict = {'timestamp': datetime.now,
                       'source': (lambda: __appname__)}

    def __init__(self, source: str) -> None:
        """Setup logger with custom callback for `source`."""
        super().__init__()
        self.source = source
        self.callbacks = {**self.callbacks, 'source': (lambda: source)}

    @property
    def handlers(self) -> List[handlers.Handler]:
        """Override of local handlers to global list."""
        global _handlers
        return _handlers

    # FIXME: explicitly named aliases to satisfy pylint;
    #        these levels are already available but pylint complains
    debug: Callable[[str], None]
    info: Callable[[str], None]
    warning: Callable[[str], None]
    error: Callable[[str], None]
    critical: Callable[[str], None]


# if not TTY suppress colors
ISATTY = sys.stderr.isatty()


@dataclass
class StandardHandler(handlers.Handler):
    """Format messages with only their source - colorized by level."""

    level: levels.Level
    resource: io.TextIOWrapper = sys.stderr

    def format(self, msg: Message) -> str:
        """Colorize the log level and with only the message."""
        color = '' if not ISATTY else Logger.colors[msg.level.value].foreground
        reset = '' if not ISATTY else RESET
        return f'{color}{msg.source}: {msg.content}{reset}'


@dataclass
class DetailedHandler(handlers.Handler):
    """Format messages in syslog style."""

    level: levels.Level
    resource: io.TextIOWrapper = sys.stderr

    def format(self, msg: Message) -> str:
        """Syslog style with padded spaces."""
        timestamp = msg.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        return f'{timestamp} {HOST} {msg.level.name:<8} {msg.source}: {msg.content}'


DETAILED_HANDLER = DetailedHandler(LEVELS[2])
STANDARD_HANDLER = StandardHandler(LEVELS[2])
_handlers.append(STANDARD_HANDLER)   # needed for errors here


# derive initial logging level from environment
INITIAL_LEVEL = os.getenv('HYPERSHELL_LOGGING_LEVEL', 'WARNING')
try:
    INITIAL_LEVEL = LEVELS_BY_NAME[INITIAL_LEVEL]
except KeyError:
    try:
        INITIAL_LEVEL = int(INITIAL_LEVEL)
        if 0 <= INITIAL_LEVEL <= 4:
            INITIAL_LEVEL = LEVELS[INITIAL_LEVEL]
        else:
            raise ValueError()
    except (ValueError, IndexError):
        Logger(__name__).critical(f'unknown: HYPERSHELL_LOGGING_LEVEL={INITIAL_LEVEL}')
        sys.exit(exit_status.runtime_error)


HANDLERS_BY_NAME = {'STANDARD': STANDARD_HANDLER,
                    'DETAILED': DETAILED_HANDLER}

INITIAL_HANDLER = os.getenv('HYPERSHELL_LOGGING_HANDLER', 'STANDARD')
try:
    INITIAL_HANDLER = HANDLERS_BY_NAME[INITIAL_HANDLER]
except KeyError:
    Logger(__name__).critical(f'unknown: HYPERSHELL_LOGGING_HANDLER={INITIAL_HANDLER}')
    sys.exit(exit_status.runtime_error)


# set initial handler by environment variable or default
INITIAL_HANDLER.level = INITIAL_LEVEL
_handlers[0] = INITIAL_HANDLER


# NOTE: All of the command line entry-points call this function
#       to setup their logging interface.
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
