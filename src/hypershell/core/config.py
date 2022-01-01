# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Runtime configuration for HyperShell."""


# type annotations
from typing import TypeVar, Union, List

# standard libs
import os
import sys
import functools

# external libs
from cmdkit.config import Namespace, Configuration, Environ, ConfigurationError  # noqa: unused import
from cmdkit.app import exit_status

# internal libs
from hypershell.core.platform import path
from hypershell.core.exceptions import write_traceback

# public interface
__all__ = ['default', 'config', 'load', 'update', 'load_task_env', ]


DEFAULT_LOGGING_STYLE = 'default'
LOGGING_STYLES = {
    'default': {
        'format': ('%(ansi_bold)s%(ansi_level)s%(levelname)8s%(ansi_reset)s %(ansi_faint)s[%(name)s]%(ansi_reset)s'
                   ' %(message)s'),
    },
    'long': {
        'format': '%(asctime)s.%(msecs)03d %(hostname)s %(levelname)8s [%(name)s] %(message)s',
    },
    'fancy': {
        'format': ('%(ansi_faint)s%(asctime)s.%(msecs)03d %(hostname)s %(ansi_reset)s'
                   '%(ansi_level)s%(ansi_bold)s%(levelname)8s%(ansi_reset)s '
                   '%(ansi_faint)s[%(name)s]%(ansi_reset)s %(message)s'),
    }
}


# environment variables and configuration files are automatically
# depth-first merged with defaults
default = Namespace({
    'database': {
        'provider': 'sqlite',
    },
    'logging': {
        'color': True,
        'level': 'warning',
        'datefmt': '%Y-%m-%d %H:%M:%S',
        'style': DEFAULT_LOGGING_STYLE,
        **LOGGING_STYLES.get(DEFAULT_LOGGING_STYLE),
    },
    'submit': {
        'bundlesize': 1,
        'bundlewait': 5  # seconds
    },
    'server': {
        'bind': 'localhost',
        'port': 50_001,
        'auth': '__HYPERSHELL__BAD__AUTHKEY__',
        'queuesize': 1,  # only allow a single bundle (scheduler must wait)
        'bundlesize': 1,
        'attempts': 1,
        'eager': False,  # prefer failed tasks to new tasks
        'wait': 5,  # seconds to wait between database queries
        'evict': 600,  # assume client is gone if no heartbeat after this many seconds
    },
    'client': {
        'bundlesize': 1,
        'bundlewait': 5,  # Seconds
        'heartrate': 10,  # Seconds, period to wait between heartbeats
    },
    'export': {
        # NOTE: defining HYPERSHELL_EXPORT_XXX defines XXX within task env
    }
})


@functools.lru_cache(maxsize=None)
def load_file(filepath: str) -> Namespace:
    """Load configuration file manually."""
    try:
        if not os.path.exists(filepath):
            return Namespace({})
        else:
            return Namespace.from_toml(filepath)
    except Exception as err:
        raise ConfigurationError(f'(from file: {filepath}) {err.__class__.__name__}: {err}')


@functools.lru_cache(maxsize=None)
def load_env() -> Environ:
    """Load environment variables and expand hierarchy as namespace."""
    return Environ(prefix='HYPERSHELL').expand()


def load(**preload: Namespace) -> Configuration:
    """Load configuration from files and merge environment variables."""
    return Configuration(**{
        **preload,
        'default': default,
        'system': load_file(path.system.config),
        'user': load_file(path.user.config),
        'local': load_file(path.local.config),
        'env': load_env(),
    })


try:
    config = load()
except Exception as error:
    write_traceback(error)
    sys.exit(exit_status.bad_config)


def get_logging_style() -> str:
    """Get and check valid on `config.logging.style`."""
    style = config.logging.style
    source = config.which('logging', 'style')
    label = '<default>'
    if source == 'env':
        label = f'HYPERSHELL_LOGGING_LEVEL={style}'
    elif source != 'default':
        label = f'from file: {path.get(source).config}'
    if not isinstance(style, str):
        raise ConfigurationError(f'Invalid logging style ({label})')
    style = style.lower()
    if style in LOGGING_STYLES:
        return style
    else:
        raise ConfigurationError(f'Unrecognized logging style \'{style}\' ({label})')


try:
    # Rebuild configuration with preloads
    config = load(logging=Namespace({'logging': LOGGING_STYLES.get(get_logging_style())}))
except Exception as error:
    write_traceback(error)
    sys.exit(exit_status.bad_config)


def update(scope: str, data: dict) -> None:
    """Extend the current configuration and commit it to disk."""
    config_path = path[scope].config
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    new_config = Namespace.from_local(config_path)
    new_config.update(data)
    new_config.to_local(config_path)


T = TypeVar('T')
def __collapse_if_list_impl(value: Union[T, List[str]]) -> Union[T, str]:
    """If `value` is a list, collapse it to a path-like :-delimited list."""
    return value if not isinstance(value, list) else ':'.join([str(member) for member in value])


def __collapse_lists(ns: Namespace) -> Namespace:
    """Collapse member values if they are a list, recursively."""
    result = Namespace()
    for key, value in ns.items():
        if isinstance(value, Namespace):
            result[key] = __collapse_lists(value)
        else:
            result[key] = __collapse_if_list_impl(value)
    return result


@functools.cache
def load_task_env() -> Environ:
    """Export environment defined in `config.export`."""
    return __collapse_lists(config.export).to_env().flatten()
