# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Build and installation script for hyper-shell."""

# standard libs
import os
from setuptools import setup, find_packages

# metadata
from hyper_shell.__meta__ import (__appname__, __version__, __description__,
                                  __authors__, __contact__, __keywords__,
                                  __license__, __website__)


with open('README.rst', mode='r') as readme:
    long_description = readme.read()


# basic dependencies
DEPS = ['cmdkit==1.5.5', 'logalpha==2.0.2', 'psutil>=5.7.0']

# add dependencies for readthedocs.io
if os.environ.get('READTHEDOCS') == 'True':
    DEPS.extend(['sphinxbootstrap4theme'])


setup(
    name             = __appname__,
    version          = __version__,
    author           = __authors__,
    author_email     = __contact__,
    description      = ' '.join(__description__.strip().split('\n')),
    license          = __license__,
    keywords         = __keywords__,
    url              = __website__,
    packages         = find_packages(),
    include_package_data = True,
    long_description = long_description,
    long_description_content_type = 'text/x-rst',
    classifiers      = ['Development Status :: 4 - Beta',
                        'Topic :: Utilities',
                        'Programming Language :: Python :: 3.7',
                        'Programming Language :: Python :: 3.8',
                        'Programming Language :: Python :: 3.9',
                        'Operating System :: POSIX :: Linux',
                        'Operating System :: MacOS',
                        'Operating System :: Microsoft :: Windows',
                        'License :: OSI Approved :: Apache Software License', ],
    install_requires = DEPS,
    entry_points     = {'console_scripts': ['hyper-shell=hyper_shell.apps:main', ]},
    data_files = [
        ('share/man/man1', ['man/man1/hyper-shell.1', ])
    ],
)
