# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Runtime configuration for HyperShell."""


# type annotations
from typing import TypeVar, Union, List

# standard libs
import os
import sys
import ctypes
import functools

# external libs
from cmdkit.config import Namespace, Configuration, Environ, ConfigurationError  # noqa: unused import
from cmdkit.app import exit_status

# internal libs
from hypershell.core.ansi import faint, bold, magenta

# public interface
__all__ = ['default', 'config', 'get_site', 'init_paths', 'load', 'update', 'load_task_env', ]


def _critical(err: Union[Exception, str]) -> None:
    """Apply basic formatting to exceptions at import-time."""
    text = err if isinstance(err, str) else f'{err.__class__.__name__}: {err}'
    print(f'{bold(magenta("CRITICAL"))}{faint(":")} {text}', file=sys.stderr)


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


cwd = os.getcwd()
home = os.getenv('HOME')
if os.name == 'nt':
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() == 1
    site = Namespace(system=os.path.join(os.getenv('ProgramData'), 'HyperShell'),
                     user=os.path.join(os.getenv('AppData'), 'HyperShell'),
                     local=os.path.join(cwd, '.hypershell'))
    path = Namespace({
        'system': {
            'lib': os.path.join(site.system, 'Library'),
            'log': os.path.join(site.system, 'Logs'),
            'config': os.path.join(site.system, 'Config.toml')},
        'user': {
            'lib': os.path.join(site.user, 'Library'),
            'log': os.path.join(site.user, 'Logs'),
            'config': os.path.join(site.user, 'Config.toml')},
        'local': {
            'lib': os.path.join(site.local, 'Library'),
            'log': os.path.join(site.local, 'Logs'),
            'config': os.path.join(site.local, 'Config.toml')}
    })
else:
    is_admin = os.getuid() == 0
    site = Namespace(system='/', user=os.path.join(home, '.hypershell'),
                     local=os.path.join(cwd, '.hypershell'))
    path = Namespace({
        'system': {
            'lib': os.path.join(site.system, 'var', 'lib', 'hypershell'),
            'log': os.path.join(site.system, 'var', 'log', 'hypershell'),
            'config': os.path.join(site.system, 'etc', 'hypershell.toml')},
        'user': {
            'lib': os.path.join(site.user, 'lib'),
            'log': os.path.join(site.user, 'log'),
            'config': os.path.join(site.user, 'config.toml')},
        'local': {
            'lib': os.path.join(site.local, 'lib'),
            'log': os.path.join(site.local, 'log'),
            'config': os.path.join(site.local, 'config.toml')}
    })


def get_site() -> Namespace:
    """Retrieve path namespace for either 'system' (if admin) or 'user'."""
    return path.system if is_admin else path.user


def init_paths() -> None:
    """Automatically create necessary directories."""
    os.makedirs(get_site().get('lib'), exist_ok=True)
    os.makedirs(get_site().get('log'), exist_ok=True)


def load() -> Configuration:
    """Load configuration."""
    return Configuration.from_local(env=True, prefix='HYPERSHELL', default=default,
                                    system=path.system.config, user=path.user.config, local=path.local.config)


try:
    config = load()
except Exception as error:
    _critical(f'ConfigurationError: {error}')
    sys.exit(exit_status.bad_config)

try:
    _style = config.logging.style
    _which = config.which('logging', 'style')
    _blame = '<default>'
    if _which == 'env':
        _blame = f'HYPERSHELL_LOGGING_LEVEL={_style}'
    elif _which != 'default':
        _blame = path.get(_which).config
    if not isinstance(_style, str):
        raise ConfigurationError(f'Invalid logging style ({_blame})')
    _style = _style.lower()
    if _style not in LOGGING_STYLES:
        raise ConfigurationError(f'Unrecognized logging style \'{_style}\' ({_blame})')
except Exception as error:
    _critical(error)
    sys.exit(exit_status.bad_config)

if _style != DEFAULT_LOGGING_STYLE:
    config.extend(logging=Namespace({'logging': LOGGING_STYLES.get(_style)}))


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
