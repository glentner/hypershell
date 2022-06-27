# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Platform specific file paths and initialization."""


# standard libs
import os
import stat
import ctypes

# external libs
from cmdkit.config import Namespace

# public interface
__all__ = ['cwd', 'home', 'site', 'path', 'default_path',
           'file_permissions', 'check_private', 'set_private']


cwd = os.getcwd()
home = os.path.expanduser('~')
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


# Automatically initialize default site directories
default_path = path.system if is_admin else path.user
os.makedirs(default_path.lib, exist_ok=True)
os.makedirs(default_path.log, exist_ok=True)
os.makedirs(os.path.join(default_path.lib, 'task'), exist_ok=True)


def file_permissions(filepath: str) -> str:
    """File permissions mask as a string."""
    return stat.filemode(os.stat(filepath).st_mode)


def check_private(filepath: str) -> bool:
    """Check that `filepath` has '-rw-------' permissions."""
    return file_permissions(filepath) == '-rw-------'


def set_private(filepath: str) -> None:
    """Update permissions to make private (i.e., go-rwx)."""
    os.chmod(filepath, 33152)  # -rw-------
