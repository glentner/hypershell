# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Logging configuration for HyperShell."""


# type annotations
from typing import Dict

# standard libraries
import os
import sys
import socket
import logging
from enum import Enum

# internal libs
from hypershell.core.config import config

# public interface
__all__ = ['Logger', 'LogRecord', 'HOSTNAME', 'handler', 'level', 'initialize_logging', ]


# cached for frequent use
HOSTNAME = socket.gethostname()
NO_TTY = False if 'HYPERSHELL_FORCE_COLOR' in os.environ else not sys.stderr.isatty()


class Ansi(Enum):
    """ANSI escape sequences for colors."""
    RESET = '\033[0m'
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'


level_color: Dict[str, Ansi] = {
    'TRACE': Ansi.CYAN,
    'DEBUG': Ansi.BLUE,
    'INFO': Ansi.GREEN,
    'WARNING': Ansi.YELLOW,
    'ERROR': Ansi.RED,
    'CRITICAL': Ansi.MAGENTA
}


TRACE = logging.DEBUG - 5
logging.addLevelName(TRACE, 'TRACE')


class Logger(logging.Logger):
    """Extend Logger to implement TRACE level."""

    def trace(self, msg: str, *args, **kwargs):
        """Log 'msg % args' with severity 'TRACE'."""
        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)


# inject class back into logging library
logging.setLoggerClass(Logger)


class LogRecord(logging.LogRecord):
    """Extends LogRecord to include the hostname and ANSI color codes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hostname = HOSTNAME
        self.ansi_color = '' if NO_TTY else level_color[self.levelname].value
        self.ansi_reset = '' if NO_TTY else Ansi.RESET.value


# inject factory back into logging library
logging.setLogRecordFactory(LogRecord)


# log to stderr with user-configurable formatting
handler = logging.StreamHandler(stream=sys.stderr)
handler.setFormatter(
    logging.Formatter(config.logging.format, datefmt=config.logging.datefmt)
)


# level handled at logger level (not handler)
levelname = config.logging.level.upper()
level = TRACE if levelname == 'TRACE' else getattr(logging, levelname)


# null handler for library use
logger = logging.getLogger('hypershell')
logger.setLevel(level)
logger.addHandler(logging.NullHandler())


# called by entry-point to configure console handler
def initialize_logging() -> None:
    """Enable logging output to the console."""
    if handler not in logger.handlers:
        logger.addHandler(handler)
