# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Hyper-shell configuration."""

# standard libs
import os

# external libs
from cmdkit.config import Namespace


CONFIG_DIR = os.path.join(os.getenv('HOME'), '.hyper-shell')
def init_config() -> None:
    """Ensure the configuration directory exists."""
    os.makedirs(CONFIG_DIR, exist_ok=True)


# load environment variables
ENV_PREFIX = 'HYPERSHELL_'
ENV = Namespace.from_env(prefix=ENV_PREFIX)

# special variables
EXE = ENV.pop('HYPERSHELL_EXE', 'hyper-shell')
CWD = ENV.pop('HYPERSHELL_CWD', os.getcwd())
ENV.pop('HYPERSHELL_TASK_ID', None)  # set for each task
ENV.pop('HYPERSHELL_TASK_ARG', None)  # set for each task

# remake without prefix for runtime
ENV = Namespace({key[len(ENV_PREFIX):]: value
                for key, value in ENV.items()})
