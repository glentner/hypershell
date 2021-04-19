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
from typing import List, Dict, Any, Type, TypeVar, Union

# standard libs
import json
import logging
from uuid import uuid4 as gen_uuid
from datetime import datetime

# external libs
from sqlalchemy import Column
from sqlalchemy.orm import Query
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import Integer, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID

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


VT = TypeVar('VT', bool, int, float, str, type(None), datetime)
RT = TypeVar('RT', bool, int, float, str, type(None))


def to_json_type(value: VT) -> Union[VT, RT]:
    """Convert `value` to alternate representation for JSON."""
    return value if not isinstance(value, datetime) else value.isoformat(sep=' ')


def from_json_type(value: RT) -> Union[RT, VT]:
    """Convert `value` to richer type if possible."""
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return value


Model = declarative_base()


class Task(Model):
    """Task model."""

    __tablename__ = 'task'
    __table_args__ = {'schema': schema}

    id = Column(Text().with_variant(UUID(), 'postgresql'), primary_key=True, nullable=False)
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

    attempt = Column(Integer(), nullable=True)
    retried = Column(Boolean(), nullable=True)
    previous_id = Column(Text().with_variant(UUID(), 'postgresql'), unique=True, nullable=True)

    columns = {
        'id': str,
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
        'attempt': int,
        'retried': bool,
        'previous_id': str,
    }

    class NotFound(NotFound):
        pass

    class NotDistinct(NotDistinct):
        pass

    class AlreadyExists(AlreadyExists):
        pass

    def __repr__(self) -> str:
        """String representation of record."""
        attrs = ', '.join([f'{name}={repr(getattr(self, name))}' for name in self.columns])
        return f'Task({attrs})'

    def to_tuple(self) -> tuple:
        """Convert fields into standard tuple."""
        return tuple([getattr(self, name) for name in self.columns])

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {name: getattr(self, name) for name in self.columns}

    def to_json(self) -> str:
        """Convert record to JSON-serializable dictionary."""
        return json.dumps({key: to_json_type(value) for key, value in self.to_dict().items()})

    @classmethod
    def from_dict(cls: Type[Model], data: Dict[str, Any]) -> Task:
        """Build record from existing dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, text: str) -> Task:
        """Build record from JSON `text` string."""
        return cls.from_dict({key: from_json_type(value) for key, value in json.loads(text).items()})

    @classmethod
    def from_id(cls, id: str) -> Task:
        """Look up task by unique `id`."""
        try:
            return Session.query(cls).filter_by(id=id).one()
        except NoResultFound as error:
            raise cls.NotFound(f'No task with id={id}') from error
        except MultipleResultsFound as error:
            raise cls.NotDistinct(f'Multiple tasks with id={id}') from error

    @classmethod
    def new(cls, args: str, attempt: int = 1, **other) -> Task:
        """Create a new Task."""
        return Task(id=str(gen_uuid()), args=str(args).strip(),
                    submit_time=datetime.now().astimezone(), submit_host=hostname,
                    attempt=attempt, **other)

    @classmethod
    def query(cls) -> Query:
        """Get query interface for table with scoped session."""
        return Session.query(cls)

    @classmethod
    def add_all(cls, tasks: List[Task]) -> List[Task]:
        """Submit list of tasks to database."""
        task_ids = [task.id for task in tasks]  # NOTE: access after commit could trigger queries
        try:
            Session.add_all(tasks)
            Session.commit()
        except Exception:
            Session.rollback()
            raise
        else:
            for task_id in task_ids:
                log.debug(f'Added task ({task_id})')
            return tasks

    @classmethod
    def add(cls, task: Task) -> None:
        """Submit single task to database."""
        cls.add_all([task, ])

    @classmethod
    def count(cls) -> int:
        """Count of tasks in database."""
        return cls.query().count()

    @classmethod
    def next_unscheduled(cls, limit: int) -> List[Task]:
        """Select unscheduled tasks up to some `limit` in order of submit_time."""
        return (cls.query()
                .order_by(cls.submit_time)
                .filter(cls.schedule_time.is_(None))
                .limit(limit).all())

    @classmethod
    def next_failed(cls, attempts: int, limit: int) -> List[Task]:
        """Select failed tasks for retry up to some `limit` under given number of `attempts`."""
        return (cls.query()
                .order_by(cls.completion_time)
                .filter(cls.exit_status.isnot(None))
                .filter(cls.exit_status != 0)
                .filter(cls.attempt <= attempts)
                .filter(cls.retried.is_(False))
                .limit(limit).all())

    @classmethod
    def next(cls, limit: int, attempts: int = 1, eager: bool = False) -> List[Task]:
        """Select tasks for scheduling including failed tasks for re-scheduling."""
        if eager:
            old_tasks = cls.next_failed(attempts=attempts, limit=limit)
            log.debug(f'Selected {len(old_tasks)} previously failed tasks')
            tasks = [Task.new(args=task.args, attempt=task.attempt + 1, previous_id=task.id) for task in old_tasks]
            Task.add_all(tasks)
            Task.update_all([{'id': task.id, 'retried': True} for task in old_tasks])
            if len(tasks) < limit:
                new_tasks = Task.next_unscheduled(limit=limit - len(tasks))
                tasks.extend(new_tasks)
                log.debug(f'Selected {len(new_tasks)} new tasks')
        else:
            tasks = Task.next_unscheduled(limit=limit)
            log.debug(f'Selected {len(tasks)} new tasks')
            if len(tasks) < limit and attempts > 1:
                old_tasks = cls.next_failed(attempts=attempts, limit=limit - len(tasks))
                log.debug(f'Selected {len(old_tasks)} previously failed tasks')
                Task.update_all([{'id': task.id, 'retried': True} for task in old_tasks])
                new_tasks = [Task.new(args=task.args, attempt=task.attempt + 1, previous_id=task.id)
                             for task in old_tasks]
                Task.add_all(new_tasks)
                tasks.extend(new_tasks)
        for task in tasks:
            task.schedule_time = datetime.now().astimezone()
            task.server_host = hostname
        Session.commit()
        return tasks

    @classmethod
    def update_all(cls, changes: List[Dict[str, Any]]) -> None:
        """
        Bulk update of tasks.

        Args:
            changes (list):
                A list of dictionaries with fields representing
                the changes to make to the Task records. The 'id' should
                be included in all dictionaries.

        See Also:
            `Session.bulk_update_mappings`

        Example:
            >>> Task.update_all([
            ...     {'id': '0b1944e8-a4dd-4964-80a8-3383e187b908', 'scheduled': True},
            ...     {'id': '85075d9a-267d-4e0c-bbf2-7b0919de4cf0', 'scheduled': True}])
        """
        Session.bulk_update_mappings(cls, changes)
        Session.commit()  # FIXME: necessary?

    @classmethod
    def update(cls, id: str, **changes) -> None:
        """
        Update single task by `id` with `changes`.

        See Also:
            `Task.update_all`

        Example:
            >>> Task.update('0b1944e8-a4dd-4964-80a8-3383e187b908', scheduled=True)
        """
        cls.update_all([{'id': id, **changes}, ])

    @classmethod
    def count_remaining(cls) -> int:
        """Count of remaining unfinished tasks."""
        return cls.query().filter(cls.completion_time.is_(None)).count()
