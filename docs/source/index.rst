Hyper-Shell
===========

Release v\ |release| (:ref:`Getting Started <getting_started>`)

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

*Hyper-shell* is an elegant, cross-platform, high-performance computing
utility for processing shell commands over a distributed, asynchronous queue.

-------------------

Features
--------

|

**Simple, Scalable, Elastic**

With *hyper-shell* you can take a listing of shell commands and process them in parallel. Use
the available *cluster* mode to process locally, automatically scale out using *SSH* or
*MPI*, or configure `Parsl <https://parsl-project.org>`_ to scale elastically using an HPC scheduler
like *Slurm* or in the cloud with *Kubernetes*.

.. code-block:: none

    ➜ seq -w 10000 | hyper-shell cluster -N24 -t 'echo {}' | tail -4
    09997
    09998
    09999
    10000

|

**Flexible**

The novel feature of *hyper-shell*, however, is the ability to independently stand up the *server* on
one machine and then connect to that server using the *client* from a different environment.

Start the *hyper-shell server* and set the bind address to ``0.0.0.0`` to allow remote connections.
The server acts like a sieve, reading tasks from a file (or ``stdin``), publishing them to the queue, and
recording failed commands to a file (or ``stdout``).

.. code-block:: none

    ➜ hyper-shell server -H 0.0.0.0 -k MY_KEY < TASKFILE > TASKFILE.failed

Connect to the running server from a different host (even from a different platform, e.g., Windows).
You can connect with any number of clients from any number of hosts. The separate client connections
will each pull individual tasks off the queue asynchronously, balancing the load.

.. code-block:: none

    ➜ hyper-shell client -H host-1 -k MY_KEY > TASKFILE.out

|

**Dynamic**

Special variables are automatically defined for each individual task. For example, ``TASK_ID`` gives
a unique integer identifier for each task (regardless of which client executes the task).

Further, any environment variable defined with the ``HYPERSHELL_`` prefix will be injected into the
environment of each task, *sans prefix*.

Use ``-t`` (short for ``--template``) to execute a template, "{}" can be used to insert the incoming
task argument (alternatively, use ``TASK_ARG``). Be sure to use single quotes to delay the variable
expansion.

.. code-block:: bash

    ➜ hyper-shell cluster -t '{} >outputs/$TASK_ID.out'

|

-------------------

|

**Table of Contents**

.. toctree::
    :maxdepth: 3

    getting_started
    documentation/index
    tutorials/index
    advanced
    contributing
    philosophy
    license
