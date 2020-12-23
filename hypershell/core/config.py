# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Runtime configuration for HyperShell."""


# standard libs
import os
import ctypes
import logging

# external libs
from cmdkit.config import Namespace, Configuration


# initialize module level logger
log = logging.getLogger(__name__)


# environment variables and configuration files are automatically
# depth-first merged with defaults
DEFAULT: Namespace = Namespace({
    'database': {
        'backend': 'sqlite',
        'database': ':memory:'
    },
    'logging': {
        'level': 'warning',
        'format': '%(ansi_color)s%(levelname)s%(ansi_reset)s [%(name)s] %(msg)s',
        'datefmt': '%Y-%m-%d %H:%M:%S'
    }
})


cwd = os.getcwd()
home = os.getenv('HOME')
if os.name == 'nt':
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() == 1
    site = Namespace(system=os.path.join(os.getenv('ProgramData'), 'HyperShell'),
                     user=os.path.join(os.getenv('AppData'), 'HyperShell'),
                     local=cwd)
    path = Namespace({
        'system': {
            'lib': os.path.join(site.system, 'Library'),
            'config': os.path.join(site.system, 'Config.toml')},
        'user': {
            'lib': os.path.join(site.user, 'Library'),
            'config': os.path.join(site.user, 'Config.toml')},
        'local': {
            'lib': os.path.join(site.local, 'lib'),
            'config': os.path.join(site.local, 'config.toml')},
    })
else:
    is_admin = os.getuid() == 0
    site = Namespace(system='/', user=os.path.join(home, '.hypershell'), local=cwd)
    path = Namespace({
        'system': {
            'lib': os.path.join(site.system, 'var', 'lib', 'hypershell'),
            'config': os.path.join(site.system, 'etc', 'hypershell.toml')},
        'user': {
            'lib': os.path.join(site.user, 'lib'),
            'config': os.path.join(site.user, 'config.toml')},
        'local': {
            'lib': os.path.join(site.local, 'lib'),
            'config': os.path.join(site.local, 'config.toml')},
    })


def load() -> Configuration:
    """Load configuration."""
    return Configuration.from_local(env=True, prefix='HYPERSHELL', default=DEFAULT,
                                    system=path.system.config, user=path.user.config, local=path.local.config)


# global configuration instance is set on import (but can be reloaded)
config: Configuration = load()


def update(scope: str, data: dict) -> None:
    """
    Extend the current configuration and commit it to disk.

    Args:
        scope (str):
            Either "local", "user", or "system"
        data (dict):
            Sectioned mappable to update configuration file.

    Example:
        >>> update('user', {
        ...    'logging': {
        ...        'level': 'debug'
        ...    }
        ... })
    """
    config_path = path[scope].config
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    new_config = Namespace.from_local(config_path)
    new_config.update(data)
    new_config.to_local(config_path)
