# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Specialized client for Parsl mode."""

# type annotations
from typing import Tuple, Dict

# standard libs
import sys
from threading import Thread
from queue import Queue
from multiprocessing import JoinableQueue
from subprocess import run

# external libs
from parsl import python_app

# internal libs
from ..core.logging import logger, setup as logging_setup
from ..core.config import CWD, ENV
from ..core.task import format_cmd


SENTINEL = None
log = logger.with_name('hyper-shell.client')

# parsl function import type
CmdSpec = Tuple[str, str, Dict[str, str]]


@python_app
def execute(cmdspec: CmdSpec) -> Tuple[int, str, str]:
    """
    Execute a subprocess.

    Arguments
    ---------
    cmdspec: Tuple[str, str, Dict[str, str]]
        This contains the `cmdline` to be executed, the `cwd` for
        the subprocess and any `env` variables to set.

    Returns
    -------
    (exit_status, stdout, stderr): (int, str, str)
        The status and outputs of the command.
    """
    cmdline, cwd, env = cmdspec
    task = run(cmdline, shell=True, capture_output=True, cwd=cwd, env=env)
    return task.returncode, task.stdout.decode(), task.stderr.decode()


class ParslScheduler(Thread):
    """Pull command lines off queue and schedule using Parsl."""

    tasks: Queue = None
    futures: Queue = None
    template: str = '{}'

    def __init__(self, tasks: Queue, futures: Queue, template: str, *args,
                 debug: bool = False, verbose: bool = False, logging: bool = False, **kwargs) -> None:
        """Initialize thread with access to queues."""
        super().__init__(*args, **kwargs)
        self.tasks = tasks
        self.futures = futures
        self.template = template

        # setup logging within the thread
        logging_setup(log, debug, verbose, logging)

    def run(self) -> None:
        """Launch tasks using Parsl and put 'future' on queue."""

        for task_id, task_arg in iter(self.tasks.get, SENTINEL):
            task_line = format_cmd(task_arg, self.template)
            log.info(f'running task_id={task_id}')
            log.debug(f'running task_id={task_id}: {task_line}')
            task_future = execute((task_line, CWD, {'TASK_ID': str(task_id),
                                                    'TASK_ARG': task_arg, **ENV}))
            self.futures.put((task_id, task_line, task_future))
        self.futures.put(SENTINEL)


class ParslCollector(Thread):
    """Pull app futures off queue and wait for result."""

    futures: Queue = None
    finished: JoinableQueue = None

    def __init__(self, futures: Queue, finished: JoinableQueue, *args,
                 debug: bool = False, verbose: bool = False, logging: bool = False, **kwargs) -> None:
        """Initialize thread with access to futures queue."""
        super().__init__(*args, **kwargs)
        self.futures = futures
        self.finished = finished

        # setup logging within the thread
        logging_setup(log, debug, verbose, logging)

    def run(self) -> None:
        """Wait for results of tasks."""
        for task_id, task_line, task_future in iter(self.futures.get, SENTINEL):
            status, stdout, stderr = task_future.result()
            print(stdout, end='', flush=True, file=sys.stdout)
            print(stderr, end='', flush=True, file=sys.stderr)
            log.info(f'finished task_id={task_id}, status={status}')
            self.finished.put((task_id, task_line, status))
