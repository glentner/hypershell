# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Build and installation script for hyper-shell."""


# standard libs
import os
import re
from setuptools import setup, find_packages


# Description from README.rst
with open('README.rst', mode='r') as readme:
    long_description = readme.read()


# Metadata by parsing __init__
with open('src/hypershell/__init__.py', mode='r') as source:
    content = source.read().strip()
    metadata = {key: re.search(key + r'\s*=\s*[\'"]([^\'"]*)[\'"]', content).group(1)
                for key in ['__version__', '__authors__', '__contact__',
                            '__description__', '__license__', '__keywords__', '__website__']}


# Core dependencies
DEPS = ['cmdkit>=2.6.0', 'toml>=0.10.2', 'tomlkit>=0.11.0', 'pyyaml>=6.0',
        'sqlalchemy>=1.4.22', 'rich>=10.16.2', 'paramiko>=2.9.1']

# Dependencies for readthedocs.io
if os.environ.get('READTHEDOCS') == 'True':
    DEPS.extend([
        'sphinx>=4.1.2',
        'sphinx-sitemap',
        'sphinx-autobuild',
        'sphinxext-opengraph',
        'sphinx-inline-tabs',
        'sphinx-copybutton',
        'sphinxcontrib-details-directive',
        'furo'
    ])


setup(
    name             = 'hyper-shell',
    version          = metadata['__version__'],
    author           = metadata['__authors__'],
    author_email     = metadata['__contact__'],
    description      = metadata['__description__'],
    license          = metadata['__license__'],
    keywords         = metadata['__keywords__'],
    url              = metadata['__website__'],
    packages         = find_packages('src'),
    package_dir      = {'': 'src', },
    include_package_data = True,
    long_description = long_description,
    long_description_content_type = 'text/x-rst',
    classifiers      = ['Development Status :: 5 - Production/Stable',
                        'Topic :: Utilities',
                        'Programming Language :: Python :: 3.9',
                        'Programming Language :: Python :: 3.10',
                        'Programming Language :: Python :: 3.11',
                        'Operating System :: POSIX :: Linux',
                        'Operating System :: MacOS',
                        'Operating System :: Microsoft :: Windows',
                        'License :: OSI Approved :: Apache Software License', ],
    install_requires = DEPS,
    extras_require = {
        'postgres': ['psycopg2>=2.9.1', ],
    },
    entry_points     = {'console_scripts': ['hyper-shell=hypershell:main', ]},
    data_files = [
        ('share/man/man1', ['man/man1/hyper-shell.1', ])
    ],
)
