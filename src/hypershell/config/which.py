# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Check origin of configuration variable."""


# standard libs
import logging

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface

# internal libs
from hypershell.core.platform import path
from hypershell.core.config import config

# public interface
__all__ = ['WhichConfigApp', ]


PROGRAM = 'hyper-shell config which'
USAGE = f"""\
usage: {PROGRAM} [-h] SECTION[...].VAR
{__doc__}\
"""

HELP = f"""\
{USAGE}

arguments:
SECTION[...].VAR        Path to variable.

options:
-h, --help              Show this message and exit.\
"""


# application logger
log = logging.getLogger(__name__)


class WhichConfigApp(Application):
    """Application class for config which command."""

    interface = Interface(PROGRAM, USAGE, HELP)

    varpath: str = None
    interface.add_argument('varpath', metavar='VAR')

    def run(self) -> None:
        """Business logic for `config which`."""
        try:
            site = config.which(*self.varpath.split('.'))
        except KeyError:
            self.log_critical(f'"{self.varpath}" not found')
            return
        if site in ('default', 'env', 'logging', ):
            print(site)
        else:
            print(f'{site}: {path[site].config}')
