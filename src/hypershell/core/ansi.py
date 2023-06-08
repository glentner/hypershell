# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""ANSI color codes and methods."""


# type annotations
from __future__ import annotations
from typing import Callable

# standard libs
import os
import re
import sys
import functools
from enum import Enum

# public interface
__all__ = ['NO_COLOR', 'FORCE_COLOR', 'COLOR_STDOUT', 'COLOR_STDERR', 'Ansi', 'format_ansi',
           'bold', 'faint', 'italic', 'underline',
           'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
           'colorize_usage', ]


# Enable/disable colors if necessary
NO_COLOR = False if not os.getenv('NO_COLOR') else True
FORCE_COLOR = False if not os.getenv('FORCE_COLOR') else True

COLOR_STDOUT = True
COLOR_STDERR = True
if not sys.stdout.isatty() and not FORCE_COLOR:
    COLOR_STDOUT = False
if not sys.stderr.isatty() and not FORCE_COLOR:
    COLOR_STDERR = False
if NO_COLOR:
    COLOR_STDOUT = False
    COLOR_STDERR = False


class Ansi(Enum):
    """ANSI escape sequences for colors."""
    NULL = ''
    RESET = '\033[0m'
    BOLD = '\033[1m'
    FAINT = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'


def format_ansi(seq: Ansi, text: str) -> str:
    """Apply escape sequence with reset afterward."""
    if NO_COLOR:
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


def colorize_usage(text: str) -> str:
    """
    Apply rich ANSI formatting to usage and help text.
    Has no effect if NO_COLOR is set or stdout is not a TTY.
    """
    if not COLOR_STDOUT:  # NOTE: usage is on stdout not stderr
        return text
    else:
        return _apply_formatters(text,
                                 _format_headers,
                                 _format_options,
                                 _format_special_args,
                                 _format_special_marker,
                                 _format_single_quoted_string,
                                 _format_double_quoted_string,
                                 _format_backtick_string,
                                 _format_digit,
                                 _format_external_commands,
                                 )


def _apply_formatters(text: str, *formatters: Callable[[str], str]) -> str:
    """Apply all usage text formatters."""
    if formatters:
        return formatters[0](_apply_formatters(text, *formatters[1:]))
    else:
        return text


# Look-around pattern to negate matches within quotation
# Whole quotations are formatted together
NOT_QUOTED = (
    r'(?=([^"]*"[^"]*")*[^"]*$)' +
    r"(?=([^']*'[^']*')*[^']*$)" +
    r'(?=([^`]*`[^`]*`)*[^`]*$)'
)


def _format_headers(text: str) -> str:
    """Add rich ANSI formatting to section headers."""
    names = ['Usage', 'Commands', 'Arguments', 'Modes', 'Options', 'Files']
    return re.sub(r'(?P<name>' + '|'.join(names) + r'):' + NOT_QUOTED, bold(r'\g<name>:'), text)


def _format_options(text: str) -> str:
    """Add rich ANSI formatting to option syntax."""
    option_pattern = r'(?P<leader>[ /\[,])(?P<option>-[a-zA-Z]|--[a-z]+(-[a-z]+)?)\b'
    return re.sub(option_pattern + NOT_QUOTED, r'\g<leader>' + cyan(r'\g<option>'), text)


def _format_special_args(text: str) -> str:
    """Add rich ANSI formatting to special argument syntax."""
    metavars = ['FILE', 'PATH', 'ARGS', 'ID', 'NUM', 'CMD', 'SIZE', 'SEC', 'NAME', 'TEMPLATE', 'CHAR', 'MODE',
                'ADDR', 'HOST', 'PORT', 'KEY', 'SECTION', 'VAR', 'VALUE', 'FIELD', 'COND', 'FORMAT', 'TAG']
    metavars_pattern = r'\b(?P<arg>' + '|'.join(metavars) + r')\b'
    return re.sub(metavars_pattern + NOT_QUOTED, italic(r'\g<arg>'), text)


def _format_special_marker(text: str) -> str:
    """Add rich ANSI formatting to special markers (e.g., '<stdout>')."""
    args = ['<stdout>', '<stderr>', '<stdin>', '<devnull>', '<none>', '<command>', '<args>', ]
    return re.sub(r'(?P<arg>' + '|'.join(args) + r')' + NOT_QUOTED, italic(r'\g<arg>'), text)


def _format_single_quoted_string(text: str) -> str:
    """Add rich ANSI formatting to quoted strings."""
    return re.sub(r"'(?P<subtext>.*)'", yellow(r"'\g<subtext>'"), text)


def _format_double_quoted_string(text: str) -> str:
    """Add rich ANSI formatting to quoted strings."""
    return re.sub(r'"(?P<subtext>.*)"', yellow(r'"\g<subtext>"'), text)


def _format_backtick_string(text: str) -> str:
    """Add rich ANSI formatting to quoted strings."""
    return re.sub(r'`(?P<subtext>.*)`', yellow(r'`\g<subtext>`'), text)


def _format_digit(text: str) -> str:
    """Add rich ANSI formatting to numerical digits."""
    return re.sub(r'\b(?P<num>\d+|null|NULL)\b' + NOT_QUOTED, green(r'\g<num>'), text)


def _format_external_commands(text: str) -> str:
    """Add rich ANSI formatting to external command mentions."""
    names = ['mpirun', 'mpiexec', 'srun', 'brun', 'jsrun', ]
    return re.sub(r'\b(?P<name>' + '|'.join(names) + r')\b' + NOT_QUOTED, italic(r'\g<name>'), text)
