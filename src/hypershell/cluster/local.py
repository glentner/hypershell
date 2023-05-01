# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Local cluster implementation."""


# type annotations
from __future__ import annotations
from typing import Iterable, IO

# standard libs
import time
import secrets

# internal libs
from hypershell.core.thread import Thread
from hypershell.core.logging import Logger
from hypershell.core.template import DEFAULT_TEMPLATE
from hypershell.submit import DEFAULT_BUNDLEWAIT
from hypershell.server import ServerThread, DEFAULT_BUNDLESIZE, DEFAULT_ATTEMPTS
from hypershell.client import ClientThread, DEFAULT_DELAY

# public interface
__all__ = ['run_local', 'LocalCluster']

# initialize logger
log = Logger.with_name(__name__)


def run_local(**options) -> None:
    """Run local cluster until completion."""
    thread = LocalCluster.new(**options)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


class LocalCluster(Thread):
    """Run server with single local client."""

    server: ServerThread
    client: ClientThread

    def __init__(self: LocalCluster,
                 source: Iterable[str] = None, num_tasks: int = 1, template: str = DEFAULT_TEMPLATE,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 in_memory: bool = False, no_confirm: bool = False,
                 forever_mode: bool = False, restart_mode: bool = False,
                 max_retries: int = DEFAULT_ATTEMPTS, eager: bool = False,
                 redirect_failures: IO = None, redirect_output: IO = None, redirect_errors: IO = None,
                 delay_start: float = DEFAULT_DELAY, capture: bool = False) -> None:
        """Initialize server and client threads."""
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, in_memory=in_memory, no_confirm=no_confirm,
                                   bundlesize=bundlesize, bundlewait=bundlewait,
                                   max_retries=max_retries, eager=eager, forever_mode=forever_mode,
                                   restart_mode=restart_mode, redirect_failures=redirect_failures)
        self.client = ClientThread(num_tasks=num_tasks, template=template, auth=auth, no_confirm=no_confirm,
                                   bundlesize=bundlesize, bundlewait=bundlewait, delay_start=delay_start,
                                   redirect_output=redirect_output, redirect_errors=redirect_errors,
                                   capture=capture)
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self: LocalCluster) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        self.client.start()
        self.client.join()
        self.server.join()

    def stop(self: LocalCluster, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        self.client.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)
