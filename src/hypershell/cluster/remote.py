# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Remote cluster implementation."""

# type annotations
from __future__ import annotations
from typing import Tuple, List, Dict, IO, Iterable, Callable, Type

# standard libs
import os
import sys
import time
import secrets
from enum import Enum
from datetime import datetime, timedelta
from functools import cached_property
from subprocess import Popen

# internal libs
from hypershell.core.fsm import State, StateMachine
from hypershell.core.config import default, load_task_env
from hypershell.core.queue import QueueConfig
from hypershell.core.thread import Thread
from hypershell.core.logging import Logger, HOSTNAME
from hypershell.core.template import DEFAULT_TEMPLATE
from hypershell.data.model import Task, Client
from hypershell.client import DEFAULT_DELAY
from hypershell.submit import DEFAULT_BUNDLEWAIT
from hypershell.server import ServerThread, DEFAULT_BUNDLESIZE, DEFAULT_ATTEMPTS

# public interface
__all__ = ['run_cluster', 'RemoteCluster', 'AutoScalingCluster',
           'DEFAULT_AUTOSCALE_POLICY', 'DEFAULT_AUTOSCALE_PERIOD', 'DEFAULT_AUTOSCALE_FACTOR',
           'DEFAULT_AUTOSCALE_INIT_SIZE', 'DEFAULT_AUTOSCALE_MIN_SIZE', 'DEFAULT_AUTOSCALE_MAX_SIZE',
           'DEFAULT_AUTOSCALE_LAUNCHER', ]

# initialize logger
log = Logger.with_name('hypershell.cluster')


def run_cluster(autoscaling: bool = False, **options) -> None:
    """Run remote cluster until completion."""
    if autoscaling:
        thread = AutoScalingCluster.new(**options)
    else:
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
                 capture: bool = False,
                 client_timeout: int = None,
                 task_timeout: int = None) -> None:
        """Initialize server and client threads with external launcher."""
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
        if client_timeout is not None:
            client_args += f' -T {client_timeout}'
        if task_timeout is not None:
            client_args += f' -W {task_timeout}'
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


# Autoscaling configuration constants
DEFAULT_AUTOSCALE_POLICY: str = default.autoscale.policy
DEFAULT_AUTOSCALE_FACTOR: float = default.autoscale.factor
DEFAULT_AUTOSCALE_PERIOD: int = default.autoscale.period
DEFAULT_AUTOSCALE_INIT_SIZE: int = default.autoscale.size.init
DEFAULT_AUTOSCALE_MIN_SIZE: int = default.autoscale.size.min
DEFAULT_AUTOSCALE_MAX_SIZE: int = default.autoscale.size.max
DEFAULT_AUTOSCALE_LAUNCHER: str = default.autoscale.launcher


class AutoScalerState(State, Enum):
    """Finite states for AutoScaler."""
    START = 0
    INIT = 1
    WAIT = 2
    CHECK = 3
    CHECK_FIXED = 4
    CHECK_DYNAMIC = 5
    SCALE = 6
    CLEAN = 7
    FINAL = 8
    HALT = 9


class AutoScalerPolicy(Enum):
    """Allowed scaling policies."""
    FIXED = 1
    DYNAMIC = 2

    @classmethod
    def from_name(cls: Type[AutoScalerPolicy], name: str) -> AutoScalerPolicy:
        """Return decided enum type from name."""
        try:
            return cls[name.upper()]
        except KeyError:
            raise RuntimeError(f'Unknown {cls.__name__} \'{name}\'')


class AutoScalerPhase(Enum):
    """Launch phase."""
    INIT = 1
    STEADY = 2
    STOP = 3


class AutoScaler(StateMachine):
    """Monitor task pressure and scale accordingly."""

    policy: AutoScalerPolicy
    factor: float
    period: int
    init_size: int
    min_size: int
    max_size: int
    launcher: str

    clients: List[Popen]
    last_check: datetime
    wait_check: timedelta

    phase: AutoScalerPhase = AutoScalerPhase.INIT
    state: AutoScalerState = AutoScalerState.START
    states: Type[State] = AutoScalerState

    def __init__(self: AutoScaler,
                 policy: str = DEFAULT_AUTOSCALE_POLICY,
                 factor: float = DEFAULT_AUTOSCALE_FACTOR,
                 period: int = DEFAULT_AUTOSCALE_PERIOD,
                 init_size: int = DEFAULT_AUTOSCALE_INIT_SIZE,
                 min_size: int = DEFAULT_AUTOSCALE_MIN_SIZE,
                 max_size: int = DEFAULT_AUTOSCALE_MAX_SIZE,
                 launcher: str = DEFAULT_AUTOSCALE_LAUNCHER,
                 ) -> None:
        """Initialize with scaling parameters."""
        self.policy = AutoScalerPolicy.from_name(policy)
        self.factor = factor
        self.period = period
        self.init_size = init_size
        self.min_size = min_size
        self.max_size = max_size
        self.launcher = launcher
        self.last_check = datetime.now()
        self.wait_check = timedelta(seconds=period)
        self.clients = []

    @cached_property
    def actions(self: AutoScaler) -> Dict[AutoScalerState, Callable[[], AutoScalerState]]:
        return {
            AutoScalerState.START: self.start,
            AutoScalerState.INIT: self.init,
            AutoScalerState.WAIT: self.wait,
            AutoScalerState.CHECK: self.check,
            AutoScalerState.CHECK_FIXED: self.check_fixed,
            AutoScalerState.CHECK_DYNAMIC: self.check_dynamic,
            AutoScalerState.SCALE: self.scale,
            AutoScalerState.CLEAN: self.clean,
            AutoScalerState.FINAL: self.finalize,
        }

    def start(self: AutoScaler) -> AutoScalerState:
        """Jump to INIT state."""
        log.info(f'Autoscale start (policy: {self.policy.name.lower()}, init-size: {self.init_size})')
        log.debug(f'Autoscale launcher: {self.launcher}')
        return AutoScalerState.INIT

    def init(self: AutoScaler) -> AutoScalerState:
        """Launch initial clients."""
        if len(self.clients) < self.init_size:
            return AutoScalerState.SCALE
        else:
            self.phase = AutoScalerPhase.STEADY
            return AutoScalerState.WAIT

    def wait(self: AutoScaler) -> AutoScalerState:
        """Wait for specified period of time."""
        if self.phase is AutoScalerPhase.STEADY:
            waited = datetime.now() - self.last_check
            if waited > self.wait_check:
                return AutoScalerState.CHECK
            else:
                log.trace(f'Autoscale wait ({timedelta(seconds=round(waited.total_seconds()))})')
                time.sleep(1)
                return AutoScalerState.WAIT
        else:
            return AutoScalerState.FINAL

    def check(self: AutoScaler) -> AutoScalerState:
        """Check if we need to scale up."""
        self.clean()
        self.last_check = datetime.now()
        if self.policy is AutoScalerPolicy.FIXED:
            return AutoScalerState.CHECK_FIXED
        else:
            return AutoScalerState.CHECK_DYNAMIC

    def check_fixed(self: AutoScaler) -> AutoScalerState:
        """Scaling procedure for a fixed policy cluster."""
        launched_size = len(self.clients)
        registered_size = Client.count_connected()
        task_count = Task.count_remaining()
        log.debug(f'Autoscale check (clients: {registered_size}/{launched_size}, tasks: {task_count})')
        if launched_size < self.min_size:
            log.debug(f'Autoscale min-size reached ({launched_size} < {self.min_size})')
            return AutoScalerState.SCALE
        if launched_size == 0 and task_count == 0:
            return AutoScalerState.WAIT
        if launched_size == 0 and task_count > 0:
            log.debug(f'Autoscale adding client ({task_count} tasks remaining)')
            return AutoScalerState.SCALE
        else:
            return AutoScalerState.WAIT

    def check_dynamic(self: AutoScaler) -> AutoScalerState:
        """Scaling procedure for a dynamic policy cluster."""
        launched_size = len(self.clients)
        registered_size = Client.count_connected()
        task_count = Task.count_remaining()
        pressure = Task.task_pressure(self.factor)
        pressure_val = 'unknown' if pressure is None else f'{pressure:.2f}'
        log.debug(f'Autoscale check (pressure: {pressure_val}, '
                  f'clients: {registered_size}/{launched_size}, tasks: {task_count})')
        if launched_size < self.min_size:
            log.debug(f'Autoscale min-size reached ({launched_size} < {self.min_size})')
            return AutoScalerState.SCALE
        if pressure is not None:
            if pressure > 1:
                log.debug(f'Autoscale pressure high ({pressure:.2f})')
                if launched_size >= self.max_size:
                    log.debug(f'Autoscale max-size reached ({launched_size} >= {self.max_size})')
                    return AutoScalerState.WAIT
                else:
                    return AutoScalerState.SCALE
            else:
                log.debug(f'Autoscale pressure low ({pressure:.2f})')
                return AutoScalerState.WAIT
        else:
            if launched_size == 0 and task_count == 0:
                log.debug(f'Autoscale pause (no clients and no tasks)')
                return AutoScalerState.WAIT
            if launched_size == 0 and task_count > 0:
                log.debug(f'Autoscale adding client ({task_count} tasks remaining)')
                return AutoScalerState.SCALE
            else:
                log.debug('Autoscale pause (waiting on clients to complete initial tasks)')
                return AutoScalerState.WAIT

    def scale(self: AutoScaler) -> AutoScalerState:
        """Launch new client."""
        proc = Popen(self.launcher, shell=True, stdout=sys.stdout, stderr=sys.stderr,
                     bufsize=0, universal_newlines=True, env={**os.environ, **load_task_env()})
        log.trace(f'Autoscale adding client ({proc.pid})')
        self.clients.append(proc)
        if self.phase is AutoScalerPhase.INIT:
            return AutoScalerState.INIT
        else:
            return AutoScalerState.WAIT

    def clean(self: AutoScaler) -> None:
        """Remove clients that have exited."""
        marked = []
        for i, client in enumerate(self.clients):
            log.trace(f'Autoscale clean ({i+1}: {client.pid})')
            status = client.poll()
            if status is not None:
                marked.append(i)
                if status != 0:
                    log.warning(f'Autoscale client ({i+1}) exited with status {status}')
                else:
                    log.debug(f'Autoscale client disconnected ({client.pid})')
        self.clients = [client for i, client in enumerate(self.clients) if i not in marked]

    @staticmethod
    def finalize() -> AutoScalerState:
        """Finalize."""
        log.debug(f'Done (autoscaler)')
        return AutoScalerState.HALT


class AutoScalerThread(Thread):
    """Run AutoScaler within dedicated thread."""

    def __init__(self: AutoScalerThread,
                 policy: str = DEFAULT_AUTOSCALE_POLICY,
                 factor: float = DEFAULT_AUTOSCALE_FACTOR,
                 period: int = DEFAULT_AUTOSCALE_PERIOD,
                 init_size: int = DEFAULT_AUTOSCALE_INIT_SIZE,
                 min_size: int = DEFAULT_AUTOSCALE_MIN_SIZE,
                 max_size: int = DEFAULT_AUTOSCALE_MAX_SIZE,
                 launcher: str = DEFAULT_AUTOSCALE_LAUNCHER,
                 ) -> None:
        """Initialize task executor."""
        super().__init__(name=f'hypershell-autoscaler')
        self.machine = AutoScaler(policy=policy, factor=factor, period=period,
                                  init_size=init_size, min_size=min_size, max_size=max_size,
                                  launcher=launcher)

    def run_with_exceptions(self: AutoScalerThread) -> None:
        """Run machine."""
        self.machine.run()

    def stop(self: AutoScalerThread, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        log.warning(f'Stopping (autoscaler)')
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class AutoScalingCluster(Thread):
    """Run server with autoscaling remote clients via external launcher."""

    server: ServerThread
    clients: Dict[str, Popen]
    launch_argv: str

    def __init__(self: AutoScalingCluster,
                 source: Iterable[str] = None,
                 num_tasks: int = 1,
                 template: str = DEFAULT_TEMPLATE,
                 bundlesize: int = DEFAULT_BUNDLESIZE,
                 bundlewait: int = DEFAULT_BUNDLEWAIT,
                 bind: Tuple[str, int] = ('0.0.0.0', QueueConfig.port),
                 delay_start: float = DEFAULT_DELAY,
                 launcher: str = DEFAULT_AUTOSCALE_LAUNCHER,
                 launcher_args: List[str] = None,
                 remote_exe: str = 'hyper-shell',
                 max_retries: int = DEFAULT_ATTEMPTS,
                 eager: bool = False,
                 redirect_failures: IO = None,
                 capture: bool = False,
                 policy: str = DEFAULT_AUTOSCALE_POLICY,
                 period: int = DEFAULT_AUTOSCALE_PERIOD,
                 factor: float = DEFAULT_AUTOSCALE_FACTOR,
                 init_size: int = DEFAULT_AUTOSCALE_INIT_SIZE,
                 min_size: int = DEFAULT_AUTOSCALE_MIN_SIZE,
                 max_size: int = DEFAULT_AUTOSCALE_MAX_SIZE,
                 forever_mode: bool = False,  # noqa: ignored (passed by ClusterApp)
                 restart_mode: bool = False,  # noqa: ignored (passed by ClusterApp)
                 in_memory: bool = False,  # noqa: ignored (passed by ClusterApp)
                 no_confirm: bool = False,  # noqa: ignored (passed by ClusterApp)
                 client_timeout: int = None,
                 task_timeout: int = None
                 ) -> None:
        """Initialize server and autoscaler."""
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, bundlesize=bundlesize, bundlewait=bundlewait,
                                   max_retries=max_retries, eager=eager, address=bind, forever_mode=True,
                                   redirect_failures=redirect_failures)
        launcher_args = '' if launcher_args is None else ' '.join(launcher_args)
        client_args = '' if not capture else '--capture'
        if client_timeout is not None:
            client_args += f' -T {client_timeout}'
        if task_timeout is not None:
            client_args += f' -W {task_timeout}'
        launcher = (f'{launcher} {launcher_args} {remote_exe} client -H {HOSTNAME} -p {bind[1]} '
                    f'-N {num_tasks} -b {bundlesize} -w {bundlewait} -t "{template}" -k {auth} '
                    f'-d {delay_start} {client_args}')
        self.autoscaler = AutoScalerThread(policy=policy, factor=factor, period=period,
                                           init_size=init_size, min_size=min_size, max_size=max_size,
                                           launcher=launcher)
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self: AutoScalingCluster) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        self.autoscaler.start()
        self.autoscaler.join()
        self.server.join()

    def stop(self: AutoScalingCluster, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        self.autoscaler.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)
