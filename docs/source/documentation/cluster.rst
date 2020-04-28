Cluster Usage
=============

The *cluster* command is a convenience method that automates the process of launching
the server and clients under a few common scenarios.

On a single machine, you can launch a specific number of clients just by giving an
integer count, e.g., to launch 16 clients use ``-N16``.

To automatically launch clients from *other* machines, either *SSH* or *MPI* can be
used depending on the context. For dedicated or specifically configured hosts, *SSH*
will simply log in to and connect back. On a large, shared system such as a high-performance
computing cluster, software typically must be loaded or activated and is not necessarily
available at login. The *mpiexec* command is similar to *ssh* but with the added benefit
of having an identical environment at the destination (e.g., the current directory and
all loaded software is the same).

Finally, *hyper-shell* can use `Parsl <https://parsl-project.org>`_ to scale elastically.
*Any* valid, named configuration (from ``~/.hyper-shell/parsl_config.py``) can be
invoked. See the :ref:`Parsl <parsl_doc>` documentation page for details.

|

With no arguments, the cluster will just print a usage statement and exit.

.. code-block::

    ➜ hyper-shell cluster
    usage: hyper-shell cluster [FILE] [-f FILE] [-o FILE] [-p NUM] [-s SIZE] [-t CMD] [-k KEY]
                               [--local [--num-cores NUM] | (--ssh | --mpi) --nodefile FILE |
                                --parsl [--profile NAME]]
                               [--verbose | --debug] [--logging]
                               [--help]

    Run the hyper-shell cluster.
    This launches clients using one of the available schemes.


|

-------------------

Each parallelism mode is mutually exclusive. The associated partner options are only
valid if given with their parent launcher.

|

``--local`` [ ``-N`` | ``--num-cores``   ``NUM`` ]
    Launch clients locally. A new client process will be started for each "core"
    requested. By default, it will launch as many clients as there are cores on
    the machine. These clients will launch using the exact path to the current
    executable.

|

``--ssh`` [ ``--nodefile``   ``FILE`` ]
    Launch clients with SSH. The *nodefile* should enumerate the hosts to be
    used. An SSH session will be created for every line in this file.
    SSH-keys should be setup to allow password-less connections. If it exists,
    a global ``~/.hyper-shell/nodefile`` can be used as the default.

|

``--mpi`` **[** ``--nodefile``   ``FILE`` **]**
    Launch clients with MPI. The *FILE* is passed to the ``-machinefile`` option
    for ``mpiexec``. If not given, rely on ``mpiexec`` to know what to do.

|

``--parsl`` **[** ``--profile``   ``NAME`` **]**
    Launch a single client to run in *parsl* mode. This loads a
    ``parsl.config.Config`` object from ``~/.hyper-shell/parsl_config.py``. If
    not specified, the profile defaults to "local", which just uses some number
    of threads locally.

|

-------------------

These options are passed through to either the server or the client invocation.

|

``-f``, ``--failed``   ``FILE``
    A file path to write commands which exited with a non-zero status. If not
    specified, nothing will be written.

|

``-o``, ``--output``   ``FILE``
    A file path to write the output of commands. By default, if this option is
    not specified, all command outputs will be redirected to ``stdout`` .

|

``-s``, ``--maxsize``   ``SIZE``
    Maximum size of the queue (default: 10000). To avoid the server queueing up
    too many tasks, this will force the server to block if clients have not yet
    taken enough commands. This is helpful for pipelines.

|

``-t``, ``--template``   ``CMD``
    Template command (default: ``"{}"``).

|

See the :ref:`network <network>` and :ref:`logging <logging>` pages for details
on those options.

.. toctree::
    :maxdepth: 3
    :hidden:
