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

.. image:: https://pepy.tech/badge/hyper-shell
    :target: https://pepy.tech/badge/hyper-shell
    :alt: Downloads

|

*HyperShell* is an elegant, cross-platform, high-performance computing utility for
processing shell commands over a distributed, asynchronous queue. It is a highly
scalable workflow automation tool for *many-task* scenarios.

There are several existing tools that serve a similar purpose, but lack some aspect
that HyperShell provides (e.g., distributed, detailed logging, automated retries,
super scale). Novel aspects of HyperShell include but are not limited to
(1) cross-platform, (2) client-server design, (3) staggered launch for large scales,
(4) persistent hosting of the server, and optionally (5) a database in-the-loop for
restarts and persisting task metadata.

*HyperShell* is pure Python and has been tested on Linux, macOS, and Windows 10 in
Python 3.9 environments. The server and clients don't even need to use the same
platform.


Installation
------------

To install *hyper-shell*:

.. code-block::

    $ pip install hyper-shell


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
