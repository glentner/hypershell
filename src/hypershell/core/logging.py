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


# Cached for later use
HOSTNAME = socket.gethostname()

# Automatically disable colors
NO_TTY = False
if not sys.stderr.isatty() or not config.logging.color:
    NO_TTY = True
if 'HYPERSHELL_FORCE_COLOR' in os.environ:
    NO_TTY = False


class Ansi(Enum):
    """ANSI escape sequences for colors."""
    RESET = '\033[0m' if not NO_TTY else ''
    BOLD = '\033[1m' if not NO_TTY else ''
    FAINT = '\033[2m' if not NO_TTY else ''
    ITALIC = '\033[3m' if not NO_TTY else ''
    UNDERLINE = '\033[4m' if not NO_TTY else ''
    BLACK = '\033[30m' if not NO_TTY else ''
    RED = '\033[31m' if not NO_TTY else ''
    GREEN = '\033[32m' if not NO_TTY else ''
    YELLOW = '\033[33m' if not NO_TTY else ''
    BLUE = '\033[34m' if not NO_TTY else ''
    MAGENTA = '\033[35m' if not NO_TTY else ''
    CYAN = '\033[36m' if not NO_TTY else ''
    WHITE = '\033[37m' if not NO_TTY else ''


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
        self.ansi_level = level_color.get(self.levelname).value
        self.ansi_reset = Ansi.RESET.value
        self.ansi_bold = Ansi.BOLD.value
        self.ansi_faint = Ansi.FAINT.value
        self.ansi_italic = Ansi.ITALIC.value
        self.ansi_underline = Ansi.UNDERLINE.value
        self.ansi_black = Ansi.BLACK.value
        self.ansi_red = Ansi.RED.value
        self.ansi_green = Ansi.GREEN.value
        self.ansi_yellow = Ansi.YELLOW.value
        self.ansi_blue = Ansi.BLUE.value
        self.ansi_magenta = Ansi.MAGENTA.value
        self.ansi_cyan = Ansi.CYAN.value
        self.ansi_white = Ansi.WHITE.value


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
