# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Logging configuration for HyperShell."""


# type annotations
from typing import Dict

# standard libraries
import sys
import socket
import logging

# external libs
from cmdkit.app import exit_status
from cmdkit.config import ConfigurationError

# internal libs
from hypershell.core.ansi import Ansi
from hypershell.core.config import config
from hypershell.core.exceptions import write_traceback

# public interface
__all__ = ['Logger', 'LogRecord', 'HOSTNAME', 'handler', 'level', 'initialize_logging', ]


# Cached for later use
HOSTNAME = socket.gethostname()


level_color: Dict[str, Ansi] = {
    'TRACE': Ansi.CYAN,
    'DEBUG': Ansi.BLUE,
    'INFO': Ansi.GREEN,
    'WARNING': Ansi.YELLOW,
    'ERROR': Ansi.RED,
    'CRITICAL': Ansi.MAGENTA
}


TRACE: int = logging.DEBUG - 5
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


class StreamHandler(logging.StreamHandler):
    """A StreamHandler that panics on exceptions in the logging configuration."""

    def handleError(self, record: LogRecord) -> None:
        """Pretty-print message and write traceback to file."""
        err_type, err_val, tb = sys.exc_info()
        write_traceback(err_val)
        sys.exit(exit_status.bad_config)


# log to stderr with user-configurable formatting
try:
    handler = StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        logging.Formatter(config.logging.format,
                          datefmt=config.logging.datefmt)
    )
except Exception as error:
    write_traceback(error)
    sys.exit(exit_status.bad_config)


try:
    levelname = config.logging.level
    if not isinstance(levelname, str):
        raise ConfigurationError(f'Unrecognized logging level \'{levelname}\'')
    levelname = levelname.upper()
    if levelname not in level_color:
        raise ConfigurationError(f'Unrecognized logging level \'{levelname}\'')
except Exception as error:
    write_traceback(error)
    sys.exit(exit_status.bad_config)


level: int = TRACE if levelname == 'TRACE' else getattr(logging, levelname)


# null handler for library use
logger = logging.getLogger('hypershell')
logger.setLevel(level)
logger.addHandler(logging.NullHandler())


# called by entry-point to configure console handler
def initialize_logging() -> None:
    """Enable logging output to the console."""
    if handler not in logger.handlers:
        logger.addHandler(handler)
