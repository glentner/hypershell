# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""SSH-based cluster implementation."""


# type annotations
from __future__ import annotations
from typing import Type, List, Iterable, Tuple, IO

# standard libs
import re
import sys
import time
import secrets
from subprocess import Popen

# external libs
from cmdkit.config import ConfigurationError, Namespace

# internal libs
from hypershell.core.config import config, blame
from hypershell.core.thread import Thread
from hypershell.core.logging import Logger, HOSTNAME
from hypershell.core.queue import QueueConfig
from hypershell.core.template import DEFAULT_TEMPLATE
from hypershell.client import DEFAULT_DELAY
from hypershell.submit import DEFAULT_BUNDLEWAIT
from hypershell.server import ServerThread, DEFAULT_BUNDLESIZE, DEFAULT_ATTEMPTS

# public interface
__all__ = ['run_ssh', 'SSHCluster', 'NodeList']

# initialize logger
log = Logger.with_name('cluster')


def run_ssh(**options) -> None:
    """Run remote ssh cluster until completion."""
    thread = SSHCluster.new(**options)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


class SSHCluster(Thread):
    """Run server with individual external ssh clients."""

    server: ServerThread
    clients: List[Popen]
    client_argv: List[str]

    def __init__(self: SSHCluster,
                 source: Iterable[str] = None, num_tasks: int = 1, template: str = DEFAULT_TEMPLATE,
                 forever_mode: bool = False, restart_mode: bool = False,
                 bind: Tuple[str, int] = ('0.0.0.0', QueueConfig.port), remote_exe: str = 'hyper-shell',
                 launcher: str = 'ssh', launcher_args: List[str] = None, nodelist: List[str] = None,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 max_retries: int = DEFAULT_ATTEMPTS, eager: bool = False, in_memory: bool = False,
                 no_confirm: bool = False, redirect_failures: IO = None, export_env: bool = False,
                 delay_start: float = DEFAULT_DELAY, capture: bool = False) -> None:
        """Initialize server and client threads."""
        if nodelist is None:
            raise AttributeError('Expected nodelist')
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, bundlesize=bundlesize, bundlewait=bundlewait,
                                   max_retries=max_retries, eager=eager, address=bind,
                                   forever_mode=forever_mode, restart_mode=restart_mode,
                                   in_memory=in_memory, no_confirm=no_confirm,
                                   redirect_failures=redirect_failures)
        launcher_env = '' if not export_env else compile_env()
        if launcher_args is None:
            launcher_args = config.ssh.get('args', '')
        else:
            launcher_args = config.ssh.get('args', '') + ' ' + ' '.join(launcher_args)
        client_args = ''
        if capture is True:
            client_args += ' --capture'
        if no_confirm:
            client_args += ' --no-confirm'
        self.client_argv = [f'{launcher} {launcher_args} {host} {launcher_env} {remote_exe} '
                            f'client -H {HOSTNAME} -p {bind[1]} -N {num_tasks} -b {bundlesize} -w {bundlewait} '
                            f'-t \'"{template}"\' -k {auth} -d {delay_start} {client_args}'
                            for host in nodelist]
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self: SSHCluster) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        self.clients = []
        for argv in self.client_argv:
            log.debug(f'Launching client: {argv}')
            self.clients.append(Popen(argv, shell=True, stdout=sys.stdout, stderr=sys.stderr))
        for client in self.clients:
            client.wait()
        self.server.join()

    def stop(self: SSHCluster, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        for client in self.clients:
            client.terminate()
        super().stop(wait=wait, timeout=timeout)


class NodeList(list):
    """A list of hostnames."""

    group_pattern: re.Pattern = re.compile(r',(?![^[]*])')
    range_pattern: re.Pattern = re.compile(r'\[((\d+|\d+-\d+)(,(\d+|\d+-\d+))*)]')

    @classmethod
    def from_cmdline(cls: Type[NodeList], arg: str = None) -> NodeList:
        """Smart initialization via some command-line `arg`."""
        if not arg:
            return cls.from_config()
        if ',' in arg or cls.range_pattern.search(arg):
            return cls.from_pattern(arg)
        else:
            return cls([arg, ])

    @classmethod
    def from_config(cls: Type[NodeList], groupname: str = None) -> NodeList:
        """Load list of hostnames from configuration file."""

        if 'ssh' not in config:
            raise ConfigurationError('No `ssh` section found in configuration')
        if 'nodelist' not in config.ssh:
            raise ConfigurationError('No `ssh.nodelist` section found in configuration')

        label = blame(config, 'ssh', 'nodelist')
        if groupname is None:
            if isinstance(config.ssh.nodelist, list):
                return cls(config.ssh.nodelist)
            elif isinstance(config.ssh.nodelist, dict):
                raise ConfigurationError(f'SSH group unspecified but multiple groups in `ssh.nodelist` ({label})')
            else:
                raise ConfigurationError(f'Expected list for `ssh.nodelist` ({label})')

        if isinstance(config.ssh.nodelist, dict):
            if groupname not in config.ssh.nodelist:
                raise ConfigurationError(f'No list \'{groupname}\' found in `ssh.nodelist` section ({label})')
            elif not isinstance(config.ssh.nodelist.get(groupname), list):
                raise ConfigurationError(f'Expected list for `ssh.nodelist.{groupname}` ({label})')
            else:
                return cls(config.ssh.nodelist.get(groupname))
        else:
            raise ConfigurationError(f'Expected either list or section for `ssh.nodelist` ({label})')

    @classmethod
    def from_pattern(cls: Type[NodeList], pattern: str) -> NodeList:
        """Expand a `pattern` to multiple hostnames."""
        pattern = pattern.strip(',')
        if match := cls.group_pattern.search(pattern):
            idx = match.start()
            return cls(cls.from_pattern(pattern[0:idx]) + cls.from_pattern(pattern[idx+1:]))
        else:
            if match := cls.range_pattern.search(pattern):
                range_spec = match.group()
                prefix, suffix = pattern.split(range_spec)
                segments = cls.expand_pattern(range_spec)
                return cls([f'{prefix}{segment}{suffix}' for segment in segments])
            else:
                return cls([pattern, ])

    @staticmethod
    def expand_pattern(spec: str) -> List[str]:
        """Take a range spec (e.g., [4,6-8]) and expand to [4,6,7,8]."""
        spec = spec.strip('[]')
        result = []
        for group in spec.split(','):
            if '-' in group:
                start_chars, stop_chars = group.strip().split('-')
                apply_padding = str if start_chars[0] != '0' else lambda s: str(s).zfill(len(start_chars))
                start, stop = int(start_chars), int(stop_chars)
                if stop < start:
                    start, stop = stop, start
                result.extend([apply_padding(value) for value in range(start, stop + 1)])
            else:
                result.extend([group, ])
        return result


def compile_env() -> str:
    """Build environment variable argument expansion for remote client launch command."""
    return ' '.join([f'{key}="{value}"' for key, value in Namespace.from_env('HYPERSHELL').items()])

