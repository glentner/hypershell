# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

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
from hypershell.core.logging import HOSTNAME, Logger
from hypershell.database.core import schema, Session

# public interface
__all__ = ['Task', 'to_json_type', 'from_json_type', ]

# module level logger
log: Logger = logging.getLogger(__name__)


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

    outpath = Column(Text(), nullable=True)
    errpath = Column(Text(), nullable=True)

    attempt = Column(Integer(), nullable=False)
    retried = Column(Boolean(), nullable=False)
    previous_id = Column(Text().with_variant(UUID(), 'postgresql'), unique=True, nullable=True)
    next_id = Column(Text().with_variant(UUID(), 'postgresql'), unique=True, nullable=True)

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
        'outpath': str,
        'errpath': str,
        'attempt': int,
        'retried': int,
        'previous_id': str,
        'next_id': str,
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
        return dict(zip(self.columns, self.to_tuple()))

    def to_json(self) -> Dict[str, RT]:
        """Convert record to JSON-serializable dictionary."""
        return {key: to_json_type(value) for key, value in self.to_dict().items()}

    def pack(self) -> bytes:
        """Encode as raw JSON bytes."""
        return json.dumps(self.to_json()).encode()

    @classmethod
    def from_dict(cls: Type[Model], data: Dict[str, VT]) -> Task:
        """Build record from existing dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, data: Dict[str, RT]) -> Task:
        """Build record from JSON `text` string."""
        return cls.from_dict({key: from_json_type(value) for key, value in data.items()})

    @classmethod
    def unpack(cls, data: bytes) -> Task:
        """Unpack raw JSON byte string."""
        return cls.from_json(json.loads(data.decode()))

    @classmethod
    def from_id(cls, id: str, caching: bool = True) -> Task:
        """Look up task by unique `id`."""
        try:
            return cls.query(caching=caching).filter_by(id=id).one()
        except NoResultFound as error:
            raise cls.NotFound(f'No task with id={id}') from error
        except MultipleResultsFound as error:
            raise cls.NotDistinct(f'Multiple tasks with id={id}') from error

    @classmethod
    def new(cls, args: str, attempt: int = 1, retried: bool = False, **other) -> Task:
        """Create a new Task."""
        return Task(id=str(gen_uuid()), args=str(args).strip(),
                    submit_time=datetime.now().astimezone(), submit_host=HOSTNAME,
                    attempt=attempt, retried=retried, **other)

    @classmethod
    def query(cls, *fields: Column, caching: bool = True) -> Query:
        """Get query interface for table with scoped session."""
        target = fields or [cls, ]
        if not caching:
            Session.expire_all()
        return Session.query(*target)

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
                log.trace(f'Added task ({task_id})')
            return tasks

    @classmethod
    def add(cls, task: Task) -> None:
        """Submit single task to database."""
        cls.add_all([task, ])

    @classmethod
    def select_new(cls, limit: int) -> List[Task]:
        """Select unscheduled tasks up to some `limit` in order of submit_time."""
        return (cls.query()
                .order_by(cls.submit_time)
                .filter(cls.schedule_time.is_(None))
                .limit(limit).all())

    @classmethod
    def select_failed(cls, attempts: int, limit: int) -> List[Task]:
        """Select failed tasks for retry up to some `limit` under given number of `attempts`."""
        return (cls.query()
                .order_by(cls.completion_time)
                .filter(cls.exit_status.isnot(None))
                .filter(cls.exit_status != 0)
                .filter(cls.attempt < attempts)
                .filter(cls.retried.is_(False))
                .limit(limit).all())

    @classmethod
    def next(cls, limit: int, attempts: int = 1, eager: bool = False) -> List[Task]:
        """Select tasks for scheduling including failed tasks for re-scheduling."""
        if eager:
            tasks = cls.__next_eager(attempts=attempts, limit=limit)
        else:
            tasks = cls.__next_not_eager(attempts, limit)
        for task in tasks:
            task.schedule_time = datetime.now().astimezone()
            task.server_host = HOSTNAME
        Session.commit()
        return tasks

    @classmethod
    def __next_eager(cls, attempts: int, limit: int) -> List[Task]:
        """Select next batch of tasks from database preferring previously failed tasks."""
        tasks = cls.__schedule_next_failed_tasks(attempts, limit)
        if len(tasks) < limit:
            new_tasks = cls.select_new(limit=limit - len(tasks))
            tasks.extend(new_tasks)
            log.trace(f'Selected {len(new_tasks)} new tasks')
        return tasks

    @classmethod
    def __next_not_eager(cls, attempts: int, limit: int) -> List[Task]:
        """Select next batch of tasks for database preferring novel tasks to old failed ones."""
        tasks = cls.select_new(limit=limit)
        log.trace(f'Selected {len(tasks)} new tasks')
        if len(tasks) < limit and attempts > 1:
            failed_tasks = cls.__schedule_next_failed_tasks(attempts=attempts, limit=limit - len(tasks))
            tasks.extend(failed_tasks)
        return tasks

    @classmethod
    def __schedule_next_failed_tasks(cls, attempts: int, limit: int) -> List[Task]:
        """Select previously failed tasks for scheduling."""
        tasks = []
        failed_tasks = cls.select_failed(attempts=attempts, limit=limit)
        if failed_tasks:
            log.trace(f'Selected {len(failed_tasks)} previously failed tasks')
            new_tasks = [cls.new(args=task.args, attempt=task.attempt + 1, previous_id=task.id)
                         for task in failed_tasks]
            tasks.extend(new_tasks)
            cls.add_all(tasks)
            cls.update_all([{'id': old_task.id, 'retried': True, 'next_id': new_task.id}
                            for old_task, new_task in zip(failed_tasks, new_tasks)])
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
        if changes:
            Session.bulk_update_mappings(cls, changes)
            Session.commit()  # NOTE: why is this necessary?
            log.trace(f'Updated {len(changes)} task(s)')

    @classmethod
    def update(cls, id: str, **changes) -> None:
        """Update single task by `id` with `changes`."""
        cls.update_all([{'id': id, **changes}, ])

    @classmethod
    def count(cls) -> int:
        """Count of tasks in database."""
        return cls.query().count()

    @classmethod
    def count_remaining(cls) -> int:
        """Count of remaining unfinished tasks."""
        return cls.query().filter(cls.completion_time.is_(None)).count()


    @classmethod
    def count_interrupted(cls) -> int:
        """Count tasks that were scheduled but not completed."""
        return (
            cls.query()
            .filter(cls.schedule_time.isnot(None))
            .filter(cls.completion_time.is_(None))
            .count()
        )

    @classmethod
    def select_interrupted(cls, limit: int) -> List[Task]:
        """Select tasks that were scheduled but not completed."""
        return (
            cls.query()
            .order_by(cls.schedule_time)
            .filter(cls.schedule_time.isnot(None))
            .filter(cls.completion_time.is_(None))
            .limit(limit)
            .all()
        )

    @classmethod
    def revert_interrupted(cls) -> None:
        """Revert scheduled but incomplete tasks to un-scheduled state."""
        while tasks := cls.select_interrupted(100):
            for task in tasks:
                task.schedule_time = None
                task.server_host = None
            Session.commit()
            for task in tasks:
                log.trace(f'Reverted previous task ({task.id})')
