# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Database interface, models, and methods."""


# standard libs
import logging

# internal libs
from hypershell.database.core import engine, Session, config, in_memory
from hypershell.database.model import Model, Task

# public interface
__all__ = ['Task', 'DATABASE_ENABLED', ]


# initialize module level logger
log = logging.getLogger(__name__)


if not in_memory:
    DATABASE_ENABLED = True
    Model.metadata.create_all(engine)
else:
    DATABASE_ENABLED = False
