# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Edit configuration file."""


# type annotations
from __future__ import annotations

# standard libs
import os
import logging
from subprocess import run

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface

# internal libs
from hypershell.core.platform import path

# public interface
__all__ = ['EditConfigApp', ]


PROGRAM = 'hyper-shell config edit'
USAGE = f"""\
usage: {PROGRAM} [-h] [--system | --user]
{__doc__}\
"""

HELP = f"""\
{USAGE}

The EDITOR/VISUAL environment variable must be set.

options:
    --system         Edit system configuration.
    --user           Edit user configuration (default).
-h, --help           Show this message and exit.\
"""


# application logger
log = logging.getLogger(__name__)


class EditConfigApp(Application):
    """Application class for config edit command."""

    interface = Interface(PROGRAM, USAGE, HELP)

    site_name: str = 'user'
    site_interface = interface.add_mutually_exclusive_group()
    site_interface.add_argument('--user', action='store_const', const='user')
    site_interface.add_argument('--system', action='store_const', const='system')

    def run(self) -> None:
        """Open editor for configuration."""

        config_path = path[self.site_name].config
        editor = os.getenv('EDITOR', os.getenv('VISUAL', None))
        if not editor:
            raise RuntimeError('EDITOR or VISUAL environment variable not defined')

        log.debug(f'Opening {config_path}')
        log.debug(f'Editor: {editor}')
        run([editor, config_path])
