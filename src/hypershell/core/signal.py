# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Signal handling facility."""


# type annotations
from __future__ import annotations
from typing import Optional, Final, Dict
from types import FrameType

# standard libs
from signal import signal as register
from signal import SIGUSR1, SIGUSR2, SIGINT, SIGTERM, SIGKILL

# internal libs
from hypershell.core.logging import Logger

# public interface
__all__ = ['check_signal', 'RECEIVED', 'SIGNAL_MAP',
           'handler', 'register_handlers', 'register',
           'SIGUSR1', 'SIGUSR2', 'SIGINT', 'SIGTERM', 'SIGKILL']


# initialize logger
log = Logger.with_name(__name__)


# Global signal value set by handler when received
RECEIVED: Optional[int] = None


def check_signal() -> Optional[int]:
    """Check for signal received and return if so."""
    return RECEIVED


SIGNAL_MAP: Final[Dict[int, str]] = {
    SIGUSR1: 'SIGUSR1',
    SIGUSR2: 'SIGUSR2',
    SIGINT:  'SIGINT',
    SIGTERM: 'SIGTERM',
    SIGKILL: 'SIGKILL',
}


def handler(signum: int, frame: Optional[FrameType]) -> None:
    """Generic handler assigns `signum` to global variable."""
    log.debug(f'Received signal {signum}: {SIGNAL_MAP.get(signum, "???")}')
    global RECEIVED
    RECEIVED = signum


def register_handlers() -> None:
    """Register signal handlers for client."""
    register(SIGUSR1, handler)
    register(SIGUSR2, handler)
