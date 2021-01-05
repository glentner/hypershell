# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Database models."""


# type annotations
from __future__ import annotations
from typing import List, Dict, Any, Type

# standard libs
import logging
from datetime import datetime

# external libs
from sqlalchemy import Column, Index, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import Integer, BigInteger, DateTime, Text

# internal libs
from hypershell.core.logging import hostname
from hypershell.database.core import schema, Session


# initialize module level logger
log = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Generic database related exception."""


class NotFound(DatabaseError):
    """Exception specific to no record found on lookup by unique field (e.g., `id`)."""


class NotDistinct(DatabaseError):
    """Exception specific to multiple records found when only one should have been."""


class AlreadyExists(DatabaseError):
    """Exception specific to a record with unique properties already existing."""


Base = declarative_base()


class Task(Base):
    """Task model."""

    __tablename__ = 'task'
    __table_args__ = {'schema': schema}

    id = Column(BigInteger().with_variant(Integer(), 'sqlite'), primary_key=True, nullable=False)
    args = Column(Text(), nullable=False)

    submit_time = Column(DateTime(timezone=True), nullable=False)
    submit_host = Column(Text(), nullable=True)
    schedule_time = Column(DateTime(timezone=True), nullable=True)

    server_host = Column(Text(), nullable=True)
    client_host = Column(Text(), nullable=True)

    command = Column(Text(), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    completion_time = Column(DateTime(timezone=True), nullable=True)
    exit_status = Column(Integer(), nullable=True)

    attempts = Column(Integer(), nullable=True)

    columns: Dict[str, type] = {
        'id': int,
        'args': str,
        'submit_time': datetime,
        'submit_host': str,
        'schedule_time': datetime,
        'server_host': str,
        'client_host': str,
        'command': str,
        'start_time': datetime,
        'completion_time': datetime,
        'exit_status': int,
        'attempts': int,
    }

    class NotFound(NotFound):
        pass

    class NotDistinct(NotDistinct):
        pass

    class AlreadyExists(AlreadyExists):
        pass

    def __repr__(self) -> str:
        """String representation of record."""
        return (f'{self.__class__.__name__}(' +
                ', '.join([f'{name}={repr(getattr(self, name))}' for name in self.columns]) +
                ')')

    def to_tuple(self) -> tuple:
        """Convert fields into standard tuple."""
        return tuple([getattr(self, name) for name in self.columns])

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {name: getattr(self, name) for name in self.columns}

    @classmethod
    def from_dict(cls: Type[Base], data: Dict[str, Any]) -> Base:
        """Build record from existing dictionary."""
        return cls(**data)

    @classmethod
    def from_id(cls, id: int) -> Task:
        """Look up task by ID."""
        try:
            return Session().query(cls).filter(cls.id == id).one()
        except NoResultFound as error:
            raise cls.NotFound(f'No task with id={id}') from error

    @classmethod
    def new(cls, args: str) -> Task:
        """Create a new Task."""
        return Task(args=str(args).strip(), submit_time=datetime.now(), submit_host=hostname)

    @classmethod
    def add_all(cls, tasks: List[Task]) -> None:
        """Submit list of tasks to database."""
        session = Session()
        try:
            session.add_all(tasks)
            session.commit()
        except Exception:
            session.rollback()
            raise

    @classmethod
    def add(cls, task: Task) -> None:
        """Submit task to database."""
        cls.add_all([task, ])

    @classmethod
    def count(cls) -> int:
        """Count of tasks in database."""
        return Session.query(cls).count()
