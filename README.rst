hyper-shell
===========

[![PyPI Version](https://img.shields.io/pypi/pyversions/hyper-shell.svg?logo=python&logoColor=white&style=flat)](https://pypi.org/project/hyper-shell/)
[![PyPI Version](https://img.shields.io/pypi/v/hyper-shell.svg?style=flat&color=blue)](https://pypi.org/project/hyper-shell/)
[![Docs Latest](https://readthedocs.org/projects/hyper-shell/badge/?version=latest&style=flat)](https://hyper-shell.readthedocs.io)
[![GitHub License](http://img.shields.io/badge/license-Apache-blue.svg?style=flat)](https://www.apache.org/licenses/LICENSE-2.0)

A cross-platform, high performance computing utility for processing shell commands
over a distributed, asynchronous queue. _hyper-shell_ is a single producer
(server) many consumer (client) system.

_hyper-shell_ is pure Python and has been tested on Linux, macOS, and Windows 10 in
Python 3.7 environments. The server and clients don't even need to be using the same
platform.


Installation
------------

To install _hyper-shell_:

```
pip install hyper-shell
```

For general use on a production system such as a shared computing cluster it is more robust
to encapsulate _hyper-shell_ within its own environment or container.


Documentation
-------------

Documentation is available at
[hyper-shell.readthedocs.io](https://hyper-shell.readthedocs.io).


Contributions
-------------

Contributions are welcome  in the form of  suggestions for additional features,  pull requests with
new features or  bug fixes, etc. If you find  bugs or have questions, open an  _Issue_ here. If and
when the project grows, a  code of conduct will be provided along side  a more comprehensive set of
guidelines for contributing; until then, just be nice.
