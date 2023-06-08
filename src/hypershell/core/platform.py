# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Platform specific file paths and initialization."""


# standard libs
import os
import sys
import ctypes

# external libs
from cmdkit.config import Namespace
from cmdkit.app import exit_status

# internal libs
from hypershell.core.ansi import bold, magenta

# public interface
__all__ = ['cwd', 'home', 'site', 'path', 'default_path']


cwd = os.getcwd()
home = os.path.expanduser('~')
if 'HYPERSHELL_SITE' not in os.environ:
    local_site = os.path.join(cwd, '.hypershell')
else:
    local_site = os.getenv('HYPERSHELL_SITE')
    if not os.path.isdir(local_site):
        print(f'{bold(magenta("CRITICAL"))} [{__name__}] '
              f'Directory does not exist (HYPERSHELL_SITE={local_site})', file=sys.stderr)
        sys.exit(exit_status.bad_config)


if os.name == 'nt':
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() == 1
    site = Namespace(system=os.path.join(os.getenv('ProgramData'), 'HyperShell'),
                     user=os.path.join(os.getenv('AppData'), 'HyperShell'),
                     local=local_site)
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
                     local=local_site)
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


if 'HYPERSHELL_SITE' in os.environ:
    default_path = path.local
else:
    default_path = path.user if not is_admin else path.system


# Automatically initialize default site directories
default_dirs = [
    default_path.lib,
    default_path.log,
    os.path.join(default_path.lib, 'task'),
]


for default_dir in default_dirs:
    try:
        os.makedirs(default_dir, exist_ok=True)
    except PermissionError:
        pass
