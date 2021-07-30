# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""
Run full cluster with server and clients.

TODO: examples and notes
"""


# type annotations
from __future__ import annotations
from typing import IO, Optional, Iterable

# standard libs
import sys
import time
import logging
import secrets

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface

# internal libs
from hypershell import config
from hypershell.core.thread import Thread
from hypershell.client import ClientThread, DEFAULT_TEMPLATE
from hypershell.server import ServerThread, DEFAULT_BUNDLESIZE, DEFAULT_ATTEMPTS
from hypershell.submit import DEFAULT_BUNDLEWAIT

# public interface
__all__ = ['LocalCluster', 'run_cluster', 'ClusterApp', ]


# module level logger
log = logging.getLogger(__name__)


class LocalCluster(Thread):
    """Run server with single local client."""

    server: ServerThread
    client: ClientThread

    def __init__(self, source: Iterable[str] = None, template: str = DEFAULT_TEMPLATE,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 max_retries: int = DEFAULT_ATTEMPTS, eager: bool = False, live: bool = False,
                 num_tasks: int = 1) -> None:
        """Initialize server and client threads."""
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, live=live,
                                   bundlesize=bundlesize, bundlewait=bundlewait,
                                   max_retries=max_retries, eager=eager)
        self.client = ClientThread(num_tasks=num_tasks, template=template, auth=auth)
        super().__init__(name='hypershell-cluster')

    def run(self) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        self.client.start()
        self.client.join()
        self.server.join()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        self.client.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


def run_cluster(**options) -> None:
    """Run cluster until completion."""
    thread = LocalCluster.new(**options)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


APP_NAME = 'hypershell cluster'
APP_USAGE = f"""\
usage: {APP_NAME} [-h] FILE [-n INT] [-t TEMPLATE]
Run local cluster.\
"""

APP_HELP = f"""\
{APP_USAGE}

options:
-N, --num-tasks      NUM   Number of tasks to run in parallel.
-b, --bundlesize     SIZE  Size of task bundle (default: {DEFAULT_BUNDLESIZE}).
-w, --bundlewait     SEC   Seconds to wait before flushing tasks (default: {DEFAULT_BUNDLEWAIT}).
-t, --template       CMD   Command-line template pattern.
-h, --help                 Show this message and exit.\
"""


class ClusterApp(Application):
    """Cluster application."""

    name = APP_NAME
    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)

    filepath: str
    source: Optional[IO] = None
    interface.add_argument('filepath', nargs='?', default=None)

    num_tasks: int = 1
    interface.add_argument('-N', '--num-tasks', type=int, default=num_tasks)

    template: str = DEFAULT_TEMPLATE
    interface.add_argument('-t', '--template', default=template)

    bundlesize: int = config.server.bundlesize
    interface.add_argument('-b', '--bundlesize', type=int, default=bundlesize)

    bundlewait: int = config.submit.bundlewait
    interface.add_argument('-w', '--bundlewait', type=int, default=bundlewait)

    eager_mode: bool = False
    max_retries: int = DEFAULT_ATTEMPTS - 1
    interface.add_argument('-r', '--max-retries', type=int, default=max_retries)
    interface.add_argument('--eager', action='store_true')

    live_mode: bool = False
    interface.add_argument('--live', action='store_true', dest='live_mode')

    def run(self) -> None:
        """Run cluster."""
        run_cluster(source=self.source, num_tasks=self.num_tasks, template=self.template,
                    bundlesize=self.bundlesize, bundlewait=self.bundlewait,
                    max_retries=self.max_retries, live=self.live_mode)

    def __enter__(self) -> ClusterApp:
        """Open file if not stdin."""
        self.source = None
        self.filepath = self.filepath or '-'
        self.source = sys.stdin if self.filepath == '-' else open(self.filepath, mode='r')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close file if not stdin."""
        if self.source is not None and self.source is not sys.stdin:
            self.source.close()
