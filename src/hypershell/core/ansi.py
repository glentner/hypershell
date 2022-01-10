# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""ANSI color codes and methods."""

# type annotations
from __future__ import annotations

# standard libs
import os
import sys
import functools
from enum import Enum

# public interface
__all__ = ['NO_TTY', 'Ansi', 'format_ansi',
           'bold', 'faint', 'italic', 'underline',
           'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']


# Automatically disable colors if necessary
NO_TTY = False
if not sys.stderr.isatty():
    NO_TTY = True
if 'HYPERSHELL_FORCE_COLOR' in os.environ:
    NO_TTY = False


class Ansi(Enum):
    """ANSI escape sequences for colors."""
    RESET = '\033[0m' if not NO_TTY else ''
    BOLD = '\033[1m' if not NO_TTY else ''
    FAINT = '\033[2m' if not NO_TTY else ''
    ITALIC = '\033[3m' if not NO_TTY else ''
    UNDERLINE = '\033[4m' if not NO_TTY else ''
    BLACK = '\033[30m' if not NO_TTY else ''
    RED = '\033[31m' if not NO_TTY else ''
    GREEN = '\033[32m' if not NO_TTY else ''
    YELLOW = '\033[33m' if not NO_TTY else ''
    BLUE = '\033[34m' if not NO_TTY else ''
    MAGENTA = '\033[35m' if not NO_TTY else ''
    CYAN = '\033[36m' if not NO_TTY else ''
    WHITE = '\033[37m' if not NO_TTY else ''


def format_ansi(seq: Ansi, text: str) -> str:
    """Apply escape sequence with reset afterward."""
    if NO_TTY:
        return text
    elif text.endswith(Ansi.RESET.value):
        return f'{seq.value}{text}'
    else:
        return f'{seq.value}{text}{Ansi.RESET.value}'


# shorthand formatting methods
bold = functools.partial(format_ansi, Ansi.BOLD)
faint = functools.partial(format_ansi, Ansi.FAINT)
italic = functools.partial(format_ansi, Ansi.ITALIC)
underline = functools.partial(format_ansi, Ansi.UNDERLINE)
black = functools.partial(format_ansi, Ansi.BLACK)
red = functools.partial(format_ansi, Ansi.RED)
green = functools.partial(format_ansi, Ansi.GREEN)
yellow = functools.partial(format_ansi, Ansi.YELLOW)
blue = functools.partial(format_ansi, Ansi.BLUE)
magenta = functools.partial(format_ansi, Ansi.MAGENTA)
cyan = functools.partial(format_ansi, Ansi.CYAN)
white = functools.partial(format_ansi, Ansi.WHITE)
