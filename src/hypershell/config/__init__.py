# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Manage configuration."""


# standard libs
import os

# external libs
from cmdkit.app import ApplicationGroup
from cmdkit.cli import Interface

# internal libs
from hypershell.config import get, set, edit, which

# public interface
__all__ = ['ConfigApp', ]


if os.name == 'nt':
    SYSTEM_CONFIG_PATH = '%ProgramData%\\HyperShell\\Config.toml'
    USER_CONFIG_PATH = '%AppData%\\HyperShell\\Config.toml'
else:
    SYSTEM_CONFIG_PATH = '/etc/hypershell.toml'
    USER_CONFIG_PATH = '~/.hypershell/config.toml'


PROGRAM = 'hyper-shell config'
USAGE = f"""\
usage: {PROGRAM} [-h] <command> [<args>...]
{__doc__}\
"""

HELP = f"""\
{USAGE}

commands:
get                      {get.__doc__}
set                      {set.__doc__}
edit                     {edit.__doc__}
which                    {which.__doc__}

options:
-h, --help               Show this message and exit.

files:
    System:  {SYSTEM_CONFIG_PATH}
    User:    {USER_CONFIG_PATH}
"""


class ConfigApp(ApplicationGroup):
    """Manage configuration."""

    interface = Interface(PROGRAM, USAGE, HELP)
    interface.add_argument('command')

    command = None
    commands = {'get': get.GetConfigApp,
                'set': set.SetConfigApp,
                'edit': edit.EditConfigApp,
                'which': which.WhichConfigApp, }
