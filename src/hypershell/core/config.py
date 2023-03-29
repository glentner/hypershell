# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Runtime configuration for HyperShell."""


# type annotations
from __future__ import annotations
from typing import TypeVar, Union, List, Optional, Protocol

# standard libs
import os
import sys
import shutil
import tomlkit
import logging
import functools
from datetime import datetime

# external libs
from cmdkit.config import Namespace, Configuration, Environ, ConfigurationError
from cmdkit.app import exit_status

# internal libs
from hypershell.core.platform import path, home
from hypershell.core.exceptions import write_traceback

# public interface
__all__ = ['config', 'update', 'default', 'ConfigurationError', 'Namespace', 'blame',
           'load', 'reload', 'load_file', 'reload_file', 'load_env', 'reload_env', 'load_task_env',
           'DEFAULT_LOGGING_STYLE', 'LOGGING_STYLES', ]

# partial logging (not yet configured - initialized afterward)
log = logging.getLogger(__name__)


DEFAULT_LOGGING_STYLE = 'default'
LOGGING_STYLES = {
    'default': {
        'format': ('%(ansi_bold)s%(ansi_level)s%(levelname)8s%(ansi_reset)s %(ansi_faint)s[%(name)s]%(ansi_reset)s'
                   ' %(message)s'),
    },
    'system': {
        'format': '%(asctime)s.%(msecs)03d %(hostname)s %(levelname)8s [%(app_id)s] [%(name)s] %(message)s',
    },
    'detailed': {
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
    'task': {
        'cwd': os.getcwd(),
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
        'bundlewait': 5,   # seconds
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
    'ssh': {
        'config': os.path.join(home, '.ssh', 'config'),
    },
    'console': {
        'theme': 'monokai',
    },
    'export': {
        # NOTE: defining HYPERSHELL_EXPORT_XXX defines XXX within task env
    }
})


def reload_file(filepath: str) -> Namespace:
    """Force reloading configuration file."""
    if not os.path.exists(filepath):
        return Namespace({})
    try:
        return Namespace.from_toml(filepath)
    except Exception as err:
        raise ConfigurationError(f'(from file: {filepath}) {err.__class__.__name__}: {err}')


@functools.lru_cache(maxsize=None)
def load_file(filepath: str) -> Namespace:
    """Load configuration file."""
    return reload_file(filepath)


def reload_env() -> Environ:
    """Force reloading environment variables and expanding hierarchy as namespace."""
    return Environ(prefix='HYPERSHELL').expand()


@functools.lru_cache(maxsize=None)
def load_env() -> Environ:
    """Load environment variables and expand hierarchy as namespace."""
    return reload_env()


def partial_load(**preload: Namespace) -> Configuration:
    """Load configuration from files and merge environment variables."""
    return Configuration(**{
        'default': default, **preload,
        'system': load_file(path.system.config),
        'user': load_file(path.user.config),
        'local': load_file(path.local.config),
        'env': load_env(),
    })


def partial_reload(**preload: Namespace) -> Configuration:
    """Force reload configuration from files and merge environment variables."""
    return Configuration(**{
        'default': default, **preload,
        'system': reload_file(path.system.config),
        'user': reload_file(path.user.config),
        'local': reload_file(path.local.config),
        'env': reload_env(),
    })


def blame(base: Configuration, *varpath: str) -> Optional[str]:
    """Construct filename or variable assignment string based on precedent of `varpath`."""
    source = base.which(*varpath)
    if not source:
        return None
    if source in ('system', 'user', 'local'):
        return f'from: {path.get(source).config}'
    elif source == 'env':
        return 'from: HYPERSHELL_' + '_'.join([node.upper() for node in varpath])
    else:
        return f'from: <{source}>'


def get_logging_style(base: Configuration) -> str:
    """Get and check valid on `config.logging.style`."""
    style = base.logging.style
    label = blame(base, 'logging', 'style')
    if not isinstance(style, str):
        raise ConfigurationError(f'Expected string for `logging.style` ({label})')
    style = style.lower()
    if style in LOGGING_STYLES:
        return style
    else:
        raise ConfigurationError(f'Unrecognized `logging.style` \'{style}\' ({label})')


def build_preloads(base: Configuration) -> Namespace:
    """Build 'preload' namespace from base configuration."""
    return Namespace({'logging': LOGGING_STYLES.get(get_logging_style(base))})


class LoaderImpl(Protocol):
    """Loader interface for building configuration."""
    def __call__(self: LoaderImpl, **preloads: Namespace) -> Configuration: ...


def build_configuration(loader: LoaderImpl) -> Configuration:
    """Construct full configuration."""
    return loader(preload=build_preloads(base=loader()))


def load() -> Configuration:
    """Load configuration from files and merge environment variables."""
    return build_configuration(loader=partial_load)


def reload() -> Configuration:
    """Load configuration from files and merge environment variables."""
    return build_configuration(loader=partial_reload)


try:
    config = load()
except Exception as error:
    write_traceback(error, module=__name__)
    sys.exit(exit_status.bad_config)


DEFAULT_CONFIG_HEADERS = f"""\
# File automatically created on {datetime.now()}
# Settings here are merged automatically with defaults and environment variables
"""


def update(scope: str, partial: dict) -> None:
    """Extend the current configuration and commit it to disk."""
    config_path = path[scope].config
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if os.path.exists(config_path):
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        config_backup_path = os.path.join(os.path.dirname(config_path), f'.config.{timestamp}.toml')
        shutil.copy(config_path, config_backup_path)
        shutil.copystat(config_path, config_backup_path)
        log.debug(f'Created backup file ({config_backup_path})')
    else:
        with open(config_path, mode='w') as stream:
            stream.write(DEFAULT_CONFIG_HEADERS)
    with open(config_path, mode='r') as stream:
        new_config = tomlkit.parse(stream.read())
    _inplace_update(new_config, partial)
    with open(config_path, mode='w') as stream:
        tomlkit.dump(new_config, stream)


# Re-implemented from `cmdkit.config.Namespace` (but works with `tomlkit`)
def _inplace_update(original: dict, partial: dict) -> dict:
    """
    Like normal `dict.update` but if values in both are mappable, descend
    a level deeper (recursive) and apply updates there instead.
    """
    for key, value in partial.items():
        if isinstance(value, dict) and isinstance(original.get(key), dict):
            original[key] = _inplace_update(original.get(key, {}), value)
        else:
            original[key] = value
    return original


if os.name == 'nt':
    PATH_DELIMITER = ';'
else:
    PATH_DELIMITER = ':'


T = TypeVar('T')
def __collapse_if_list_impl(value: Union[T, List[str]]) -> Union[T, str]:
    """If `value` is a list, collapse it to a path-like list (with ':' or ';')."""
    return value if not isinstance(value, list) else PATH_DELIMITER.join([str(member) for member in value])


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
