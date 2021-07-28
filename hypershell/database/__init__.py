# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Database interface, models, and methods."""


# standard libs
import logging

# internal libs
from hypershell.database.core import engine, Session, config
from hypershell.database.model import Model


# initialize module level logger
log = logging.getLogger(__name__)


if hasattr(config, 'file') and config.file:
    DATABASE_ENABLED = True
    log.debug('Initializing database objects')
    Model.metadata.create_all(engine)
else:
    DATABASE_ENABLED = False
