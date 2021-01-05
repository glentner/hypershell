# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Logging configuration for HyperShell."""


# standard libraries
import socket
import logging as _logging

# external libs
from cmdkit.config import ConfigurationError

# internal libs
from hypershell.core.config import config


# cached for frequent use
hostname = socket.gethostname()


# escape sequences
ANSI_RESET = '\033[0m'
ANSI_CODES = {
    prefix: {color: '\033[{prefix}{num}m'.format(prefix=i + 3, num=j)
             for j, color in enumerate(['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'])}
    for i, prefix in enumerate(['foreground', 'background'])}
LEVEL_COLORS = {'debug': 'blue', 'info': 'green', 'warning': 'yellow',
                'error': 'red', 'critical': 'magenta'}


class LogRecord(_logging.LogRecord):
    """Extends :class:`logging.LogRecord` to include a hostname and ANSI color codes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hostname = hostname
        self.ansi_color = ANSI_CODES['foreground'][LEVEL_COLORS[self.levelname.lower()]]
        self.ansi_reset = ANSI_RESET


# inject factory back into logging library
_logging.setLogRecordFactory(LogRecord)


# called by entry-point to configure console handler
def initialize_logging() -> None:
    """Configure with func:`logging.basicConfig` for command-line interface."""
    try:
        _logging.basicConfig(level=getattr(_logging, config.logging.level.upper()),
                             format=config.logging.format,
                             datefmt=config.logging.datefmt)
    except Exception as error:
        raise ConfigurationError('Failed logging configuration') from error
