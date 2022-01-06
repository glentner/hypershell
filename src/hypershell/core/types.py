# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Automatic type coercion of input data."""


# type annotations
from typing import TypeVar

# public interface
__all__ = ['smart_coerce', 'ValueType']


# Each possible input type
ValueType = TypeVar('ValueType', bool, int, float, str, type(None))


def smart_coerce(value: str) -> ValueType:
    """Automatically coerce string to typed value."""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    if value.lower() in ('null', 'none', ):
        return None
    elif value.lower() in ('true', ):
        return True
    elif value.lower() in ('false', ):
        return False
    else:
        return value
