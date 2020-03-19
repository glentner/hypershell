hyper-shell
===========

.. image:: https://img.shields.io/badge/license-Apache-blue.svg?style=flat
    :target: https://www.apache.org/licenses/LICENSE-2.0
    :alt: License

.. image:: https://img.shields.io/pypi/v/hyper-shell.svg?style=flat&color=blue
    :target: https://pypi.org/project/hyper-shell
    :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/hyper-shell.svg?logo=python&logoColor=white&style=flat
    :target: https://pypi.org/project/hyper-shell
    :alt: Python Versions

.. image:: https://readthedocs.org/projects/hyper-shell/badge/?version=latest&style=flat
    :target: https://hyper-shell.readthedocs.io
    :alt: Documentation


A cross-platform, high performance computing utility for processing shell commands
over a distributed, asynchronous queue. *hyper-shell* is a single producer
(server) many consumer (client) system.

*hyper-shell* is pure Python and has been tested on Linux, macOS, and Windows 10 in
Python 3.7 environments. The server and clients don't even need to be using the same
platform.


Installation
------------

To install *hyper-shell*:

.. code-block::

    pip install hyper-shell

For general use on a production system such as a shared computing cluster it is more robust
to encapsulate *hyper-shell* within its own environment or module.


Documentation
-------------

Documentation is available at `hyper-shell.readthedocs.io <https://hyper-shell.readthedocs.io>`_.
For basic usage information on the command line use: ``hyper-shell --help``. For a more 
comprehensive usage guide on the command line you can view the manual page with 
``man hyper-shell``.


Contributions
-------------

Contributions are welcome in the form of suggestions for additional features, pull requests with
new features or bug fixes, etc. If you find bugs or have questions, open an *Issue* here. If and
when the project grows, a code of conduct will be provided along side a more comprehensive set of
guidelines for contributing; until then, just be nice.
