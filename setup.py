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
from setuptools import setup, find_packages


with open('README.rst', mode='r') as readme:
    long_description = readme.read()

setup(
    name             = 'hyper-shell',
    version          = '1.6.2',
    author           = 'Geoffrey Lentner',
    author_email     = 'glentner@purdue.edu',
    description      = ('A cross-platform, high performance computing utility for processing '
                        'shell commands over a distributed, asynchronous queue.'),
    license          = 'Apache Software License',
    keywords         = ('distributed-computing command-line-tool shell-scripting '
                        'high-performance-computing'),
    url              = 'https://github.com/glentner/hyper-shell',
    packages         = find_packages(),
    long_description = long_description,
    long_description_content_type = 'text/x-rst',
    classifiers      = ['Development Status :: 4 - Beta',
                        'Topic :: Utilities',
                        'Programming Language :: Python :: 3.7',
                        'Programming Language :: Python :: 3.8',
                        'Operating System :: POSIX :: Linux',
                        'Operating System :: MacOS',
                        'Operating System :: Microsoft :: Windows',
                        'License :: OSI Approved :: Apache Software License', ],
    install_requires = ['cmdkit>=1.0.0', 'logalpha>=2.0.0', 'psutil', ],
    entry_points     = {'console_scripts': ['hyper-shell=hyper_shell:main', ]},
)
