hyper-shell
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

.. include:: _include/desc.rst


-------------------

Features
--------

**Simple, Scalable, Elastic**

With *hyper-shell* you can take a listing of shell commands and process them in parallel. Use
the available *cluster* mode to process locally, automatically scale out using *SSH* or
*MPI* (or some other custom launcher), or configure `Parsl <https://parsl-project.org>`_ to scale
elastically using an HPC scheduler like *Slurm* or in the cloud with *Kubernetes*.

.. code-block:: bash
    :caption: Trivial Example

    $ seq 4 | hyper-shell cluster -N2 -t 'echo {}'
    0
    1
    2
    4

|

**Flexible**

One of several novel features of *hyper-shell*, however, is the ability to independently
stand up the *server* on one machine and then connect to that server using a *client* from
a different environment.

Start the *hyper-shell server* and set the bind address to ``0.0.0.0`` to allow remote connections.
The server schedules tasks on a distributed queue.

.. code-block:: bash
    :caption: Stand Alone Server

    $ hyper-shell server -H '0.0.0.0' -k '<AUTHKEY>' < Taskfile

Connect to the running server from a different host (even from a different platform, e.g., Windows).
You can connect with any number of clients from any number of hosts. The separate client connections
will each pull tasks off the queue asynchronously, balancing the load.

.. code-block:: bash
    :caption: Remote Client

    $ hyper-shell client -H '<HOSTNAME>' -k '<AUTHKEY>'

|

**Dynamic**

Special variables are automatically defined for each individual task. For example, ``TASK_ID`` gives
a unique UUID for each task (regardless of which client executes the task).

Further, any environment variable defined with the ``HYPERSHELL_EXPORT_`` prefix will be injected into the
environment of each task, *sans prefix*.

Use ``-t`` (short for ``--template``) to execute a template, ``{}`` can be used to insert the incoming
task arguments (alternatively, use ``TASK_ARGS``). Be sure to use single quotes to delay the variable
expansion. Many meta-patterns are supported (see full overview of :ref:`templates <templates>`:

* File operations (e.g., the basename ``'{/}'``)
* Slicing on whitespace (e.g., first ``'{[0]}'``, first three ``'{[:3]}'``, every other ``'{[::2]}'``)
* Sub-commands (e.g., ``'{% dirname @ %}'``)
* Lambda expressions in *x* (e.g., ``'{= x + 1 =}'``)

.. code-block:: bash
    :caption: Capture Output From Each Command

    $ hyper-shell cluster Taskfile -N12 -t '{} >outputs/$TASK_ID.out'

|

.. toctree::
    :caption: Intro
    :hidden:

    getting_started
    install

.. toctree::
    :hidden:
    :caption: Reference

    cli/index
    api/index
    config
    logging
    database
    templates

.. toctree::
    :caption: Tutorial
    :hidden:

    tutorial/basic
    tutorial/distributed
    tutorial/hybrid
    tutorial/advanced
    tutorial/parsl

.. toctree::
    :hidden:
    :caption: Development

    contributing
    license

