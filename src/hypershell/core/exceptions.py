# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Exception handling."""


# standard libs
import os
import traceback
from logging import Logger
from datetime import datetime

# external libs
from cmdkit.app import exit_status

# internal libs
from hypershell.core.config import get_site

# public interface
__all__ = ['handle_disconnect', 'handle_exception', 'handle_uncaught_exception', ]


def handle_disconnect(exc: Exception, logger: Logger) -> int:
    """An EOFError results from the server hanging up the client."""
    logger.critical(f'{exc.__class__.__name__}: server disconnected')
    return exit_status.runtime_error


def handle_exception(exc: Exception, logger: Logger, status: int) -> int:
    """Log the exception argument and exit with `status`."""
    msg = str(exc).replace('\n', ' - ')
    logger.critical(f'{exc.__class__.__name__}: {msg}')
    return status


def handle_uncaught_exception(exc: Exception, logger: Logger) -> int:
    """Write exception to file and return exit code."""
    time = datetime.now().strftime('%Y%m%d-%H%M%S')
    path = os.path.join(get_site()['log'], f'exception-{time}.log')
    with open(path, mode='w') as stream:
        print(traceback.format_exc(), file=stream)
    msg = str(exc).replace('\n', ' - ')
    logger.critical(f'{exc.__class__.__name__}: {msg}')
    logger.critical(f'Exception traceback written to {path}')
    return exit_status.uncaught_exception
