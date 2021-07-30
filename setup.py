# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Build and installation script for hypershell."""


# standard libs
import os
import re
from setuptools import setup, find_packages


# long description from README.rst
with open('README.rst', mode='r') as readme:
    long_description = readme.read()


# package metadata by parsing __meta__ module
with open('hypershell/__meta__.py', mode='r') as source:
    content = source.read().strip()
    metadata = {key: re.search(key + r'\s*=\s*[\'"]([^\'"]*)[\'"]', content).group(1)
                for key in ['__version__', '__authors__', '__contact__', '__description__',
                            '__license__', '__keywords__', '__website__']}


# core dependencies
DEPS = ['cmdkit>=2.3.0', 'toml>=0.10.2', 'sqlalchemy>=1.3.19', ]


# add dependencies for readthedocs.io
if os.environ.get('READTHEDOCS') == 'True':
    DEPS.extend(['pydata-sphinx-theme'])


setup(
    name             = 'hypershell',
    version          = metadata['__version__'],
    author           = metadata['__authors__'],
    author_email     = metadata['__contact__'],
    description      = metadata['__description__'],
    license          = metadata['__license__'],
    keywords         = metadata['__keywords__'],
    url              = metadata['__website__'],
    packages         = find_packages(),
    include_package_data = True,
    long_description = long_description,
    long_description_content_type = 'text/x-rst',
    classifiers      = ['Development Status :: 4 - Beta',
                        'Topic :: Utilities',
                        'Programming Language :: Python :: 3.8',
                        'Programming Language :: Python :: 3.9',
                        'Operating System :: POSIX :: Linux',
                        'Operating System :: MacOS',
                        'Operating System :: Microsoft :: Windows',
                        'License :: OSI Approved :: Apache Software License', ],
    install_requires = DEPS,
    extra_requires = {
        'postgres': ['psycopg2>=2.8.5', ],
    },
    entry_points     = {'console_scripts': ['hyper-shell=hypershell:main', ]},
    data_files = [
        ('share/man/man1', ['man/man1/hypershell.1', ])
    ],
)
