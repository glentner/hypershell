# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Logging configuration for HyperShell."""


# type annotations
from typing import Dict, Any

# standard libraries
import sys
import uuid
import socket
import logging
import functools

# external libs
from cmdkit.app import exit_status
from cmdkit.config import ConfigurationError

# internal libs
from hypershell.core.ansi import Ansi
from hypershell.core.config import config, blame
from hypershell.core.exceptions import write_traceback

# public interface
__all__ = ['Logger', 'HOSTNAME', 'handler', 'initialize_logging', ]


# Cached for later use
HOSTNAME = socket.gethostname()


# Unique for every instance of hypershell
INSTANCE = str(uuid.uuid4())


# Canonical colors for logging messages
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
        self.app_id = INSTANCE
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
        write_traceback(err_val, module=__name__)
        sys.exit(exit_status.bad_config)


def level_from_name(name: Any, source: str = 'logging.level') -> int:
    """Get level value from `name`."""
    label = blame(*source.split('.'))
    if not isinstance(name, str):
        raise ConfigurationError(f'Expected string for logging level, given \'{name}\' ({label})')
    name = name.upper()
    if name == 'TRACE':
        return TRACE
    elif name in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        return getattr(logging, name)
    else:
        raise ConfigurationError(f'Unsupported logging level \'{name}\' ({label})')


try:
    levelname = config.logging.level
    level = level_from_name(levelname)
except Exception as error:
    write_traceback(error, module=__name__)
    sys.exit(exit_status.bad_config)


try:
    handler = StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        logging.Formatter(config.logging.format,
                          datefmt=config.logging.datefmt)
    )
except Exception as error:
    write_traceback(error, module=__name__)
    sys.exit(exit_status.bad_config)


# null handler for library use
logger = logging.getLogger('hypershell')
logger.setLevel(level)
logger.addHandler(logging.NullHandler())


@functools.cache
def initialize_logging() -> None:
    """Enable logging output to the console and rotating files."""
    logger.addHandler(handler)
