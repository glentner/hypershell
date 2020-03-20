# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Get Parsl config object from file; set default config file."""

# type annotations
from typing import Dict

# standard libs
import os
import sys
import inspect
import importlib

# internal libs
from ..core import config as hyper_shell_config
from ..core.logging import logger


# only called by client
log = logger.with_name('hyper-shell.client')


CONFIG_DIR = hyper_shell_config.CONFIG_DIR
CONFIG_FILE = os.path.join(CONFIG_DIR, 'parsl_config.py')
DEFAULT_CONFIG = """\
# Hyper-shell Parsl configuration file.

# Import and create configuration objects via Parsl.
# Hyper-shell will import this module and inspect for Python
# objects by name that have type `parsl.config.Config`.

# default configuration, do not remove this line
from parsl.configs.local_threads import config as local
"""


def init_config() -> None:
    """Ensure at least the default config is present."""
    hyper_shell_config.init_config()  # ensure ~/.hyper-shell
    if not os.path.exists(CONFIG_FILE):
        log.debug('writing default parsl configuration')
        with open(CONFIG_FILE, mode='w') as config_file:
            config_file.write(DEFAULT_CONFIG)


def load_config(name: str) -> Dict[str, 'parsl.config.Config']:
    """Load config objects from module."""

    # local import relaxes parsl dependency
    from parsl import load
    from parsl.config import Config

    # initialize parsl configuration if needed
    init_config()

    # dynamically load config as a module
    sys.path.append(CONFIG_DIR)
    parsl_config = importlib.import_module('parsl_config')

    # create dictionary of config objects by name
    def is_config(member): return isinstance(member, Config)
    configs = inspect.getmembers(parsl_config, is_config)
    configs = dict(configs)

    if name not in configs:
        raise RuntimeError(f'no parsl config: "{name}"')

    load(configs[name])
    log.debug(f'loaded parsl config: {name}')
