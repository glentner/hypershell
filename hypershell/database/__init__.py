# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Database interface, models, and methods."""


# standard libs
import logging

# internal libs
from hypershell.database.core import engine, Session, config
from hypershell.database.model import Model


# initialize module level logger
log = logging.getLogger(__name__)


log.debug('Initializing database objects')
Model.metadata.create_all(engine)
