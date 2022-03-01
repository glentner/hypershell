# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Get variable from configuration file."""


# type annotations
from __future__ import annotations
from typing import Mapping, Any

# standard libs
import os
import sys
import json
import logging

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface
from rich.console import Console
from rich.syntax import Syntax
import toml

# internal libs
from hypershell.core.platform import path
from hypershell.core.config import load_file, config as full_config

# public interface
__all__ = ['GetConfigApp', ]


PROGRAM = 'hyper-shell config get'
USAGE = f"""\
usage: {PROGRAM} [-h] [-x] SECTION[...].VAR [--system | --user]
{__doc__}\
"""

HELP = f"""\
{USAGE}

arguments:
SECTION[...].VAR          Path to variable.

options:
    --system              Load from system configuration.
    --user                Load from user configuration.
-x, --expand              Expand variable.
-h, --help                Show this message and exit.\
"""


# application logger
log = logging.getLogger(__name__)


class GetConfigApp(Application):
    """Application class for config get command."""

    interface = Interface(PROGRAM, USAGE, HELP)

    varpath: str = None
    interface.add_argument('varpath', metavar='VAR')

    site_name: str = None
    site_interface = interface.add_mutually_exclusive_group()
    site_interface.add_argument('--user', action='store_const', const='user', dest='site_name')
    site_interface.add_argument('--system', action='store_const', const='system', dest='site_name')

    expand: bool = False
    interface.add_argument('-x', '--expand', action='store_true')

    def run(self) -> None:
        """Business logic for `hyper-shell config get`."""

        if self.site_name is None:
            config = full_config
        else:
            config_path = path[self.site_name].config
            if os.path.exists(config_path):
                config = load_file(config_path)
            else:
                raise RuntimeError(f'{config_path} does not exist')

        if self.varpath == '.':
            self.print_result(config)
            return

        if '.' not in self.varpath:
            if self.varpath in config:
                self.print_result(config[self.varpath])
                return
            else:
                raise RuntimeError(f'"{self.varpath}" not found in {path}')

        if self.varpath.startswith('.'):
            raise RuntimeError(f'Section name cannot start with "."')

        section, *subsections, variable = self.varpath.split('.')
        if section not in config:
            raise RuntimeError(f'"{section}" is not a section')

        config_section = config[section]
        if subsections:
            subpath = f'{section}'
            try:
                for subsection in subsections:
                    subpath += f'.{subsection}'
                    if not isinstance(config_section[subsection], Mapping):
                        raise RuntimeError(f'"{subpath}" not a section in {path}')
                    else:
                        config_section = config_section[subsection]
            except KeyError as error:
                raise RuntimeError(f'"{subpath}" not found in {path}') from error

        if self.expand:
            try:
                value = getattr(config_section, variable)
            except ValueError as error:
                raise RuntimeError(*error.args) from error
            if value is None:
                raise RuntimeError(f'"{variable}" not found in {path}')
            self.print_result(value)
            return

        if variable not in config_section:
            raise RuntimeError(f'"{self.varpath}" not found in {path}')

        self.print_result(config_section[variable])

    def print_result(self, value: Any) -> None:
        """Print the final result."""
        if isinstance(value, Mapping):
            if self.varpath == '.':
                value = toml.dumps(value)
            else:
                value = toml.dumps({self.varpath: value})
            lines = []
            for line in value.strip().split('\n'):
                if not line.startswith('['):
                    lines.append(line)
                else:
                    lines.append(line.replace('"', ''))
            value = '\n'.join(lines)
        else:
            value = json.dumps(value)  # NOTE: close enough
        if sys.stdout.isatty():
            output = Syntax(value, 'toml', word_wrap=True,
                            theme = full_config.console.theme,
                            background_color = 'default')
            Console().print(output)
        else:
            print(value, file=sys.stdout, flush=True)
