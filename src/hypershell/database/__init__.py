# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Database interface, models, and methods."""


# standard libs
import sys

# external libs
from cmdkit.app import exit_status

# internal libs
from hypershell.core.exceptions import write_traceback
from hypershell.database.core import engine, Session, config, in_memory
from hypershell.database.model import Model, Task

# public interface
__all__ = ['Task', 'DATABASE_ENABLED', ]


try:
    if not in_memory:
        DATABASE_ENABLED = True
        Model.metadata.create_all(engine)
    else:
        DATABASE_ENABLED = False
except Exception as error:
    write_traceback(error, module=__name__)
    sys.exit(exit_status.bad_config)
