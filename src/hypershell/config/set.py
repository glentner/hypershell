# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Set variable in configuration file."""


# type annotations
from __future__ import annotations
from typing import TypeVar

# standard libs
import logging

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface, ArgumentError

# internal libs
from hypershell.core.config import update
from hypershell.core.types import smart_coerce

# public interface
__all__ = ['SetConfigApp', ]


PROGRAM = 'hyper-shell config set'
USAGE = f"""\
usage: {PROGRAM} [-h] SECTION[...].VAR VALUE [--system | --user]
{__doc__}\
"""

HELP = f"""\
{USAGE}

arguments:
SECTION[...].VAR        Path to variable.
VALUE                   Value to be set.

options:
    --system            Apply to system configuration.
    --user              Apply to user configuration (default).
-h, --help              Show this message and exit.\
"""


log = logging.getLogger(__name__)


class SetConfigApp(Application):
    """Application class for config set command."""

    interface = Interface(PROGRAM, USAGE, HELP)

    varpath: str = None
    interface.add_argument('varpath', metavar='VAR')

    value: str = None
    interface.add_argument('value', type=smart_coerce)

    site_name: str = 'user'
    site_interface = interface.add_mutually_exclusive_group()
    site_interface.add_argument('--user', action='store_const', const='user', dest='site_name')
    site_interface.add_argument('--system', action='store_const', const='system', dest='site_name')

    def run(self) -> None:
        """Business logic for `config set`."""

        if '.' not in self.varpath:
            raise ArgumentError('Missing section in variable path')

        section, *subsections, variable = self.varpath.split('.')

        config = {section: {}}
        config_section = config[section]
        for subsection in subsections:
            if subsection not in config_section:
                config_section[subsection] = dict()
            config_section = config_section[subsection]

        config_section[variable] = self.value
        update(self.site_name, config)
