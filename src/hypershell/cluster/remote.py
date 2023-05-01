# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Remote cluster implementation."""

# type annotations
from __future__ import annotations
from typing import Iterable, Tuple, List, IO

# standard libs
import os
import sys
import time
import secrets
from subprocess import Popen

# internal libs
from hypershell.core.config import load_task_env
from hypershell.core.queue import QueueConfig
from hypershell.core.thread import Thread
from hypershell.core.logging import Logger, HOSTNAME
from hypershell.core.template import DEFAULT_TEMPLATE
from hypershell.client import DEFAULT_DELAY
from hypershell.submit import DEFAULT_BUNDLEWAIT
from hypershell.server import ServerThread, DEFAULT_BUNDLESIZE, DEFAULT_ATTEMPTS

# public interface
__all__ = ['run_cluster', 'RemoteCluster']

# initialize logger
log = Logger.with_name('cluster')


def run_cluster(**options) -> None:
    """Run remote cluster until completion."""
    thread = RemoteCluster.new(**options)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


class RemoteCluster(Thread):
    """Run server with remote clients via external launcher (e.g., MPI)."""

    server: ServerThread
    clients: Popen
    client_argv: str

    def __init__(self: RemoteCluster,
                 source: Iterable[str] = None,
                 num_tasks: int = 1,
                 template: str = DEFAULT_TEMPLATE,
                 bundlesize: int = DEFAULT_BUNDLESIZE,
                 bundlewait: int = DEFAULT_BUNDLEWAIT,
                 forever_mode: bool = False,
                 restart_mode: bool = False,
                 bind: Tuple[str, int] = ('0.0.0.0', QueueConfig.port),
                 delay_start: float = DEFAULT_DELAY,
                 launcher: str = 'mpirun',
                 launcher_args: List[str] = None,
                 remote_exe: str = 'hyper-shell',
                 max_retries: int = DEFAULT_ATTEMPTS,
                 eager: bool = False,
                 redirect_failures: IO = None,
                 in_memory: bool = False,
                 no_confirm: bool = False,
                 capture: bool = False) -> None:
        """Initialize server and client threads."""
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, bundlesize=bundlesize, bundlewait=bundlewait,
                                   in_memory=in_memory, no_confirm=no_confirm, max_retries=max_retries, eager=eager,
                                   address=bind, forever_mode=forever_mode, restart_mode=restart_mode,
                                   redirect_failures=redirect_failures)
        launcher_args = '' if launcher_args is None else ' '.join(launcher_args)
        client_args = ''
        if capture is True:
            client_args += ' --capture'
        if no_confirm is True:
            client_args += ' --no-confirm'
        self.client_argv = (f'{launcher} {launcher_args} {remote_exe} client -H {HOSTNAME} -p {bind[1]} '
                            f'-N {num_tasks} -b {bundlesize} -w {bundlewait} -t "{template}" -k {auth} '
                            f'-d {delay_start} {client_args}')
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self: RemoteCluster) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        log.debug(f'Launching clients: {self.client_argv}')
        self.clients = Popen(self.client_argv, shell=True, stdout=sys.stdout, stderr=sys.stderr,
                             env={**os.environ, **load_task_env()})
        self.clients.wait()
        self.server.join()

    def stop(self: RemoteCluster, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        self.clients.terminate()
        super().stop(wait=wait, timeout=timeout)
