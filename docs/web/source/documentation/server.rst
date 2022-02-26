Server Usage
============

The *server* reads command lines from a file (or ``stdin``) and publishes
them to a distributed queue.

Any command that returns a non-zero exit status will have a warning message
emitted and the original command line will be written to a file (or ``stdout``).
In this way, the server acts like a sieve, consuming commands and emitting failures.

The basic premise is as follows, for a given ``TASKFILE`` consisting of
input command lines:

.. code-block:: none

    ➜ hyper-shell server - < TASKFILE > TASKFILE.failed

The created ``TASKFILE.failed`` will contain a subset of the lines
from ``TASKFILE``.

|

With no arguments, the server will just print a usage statement and exit.

.. code-block:: none

    ➜ hyper-shell server
    usage: hyper-shell server FILE [--output FILE] [--maxsize SIZE]
                              [--host ADDR] [--port PORT] [--authkey KEY]
                              [--verbose | --debug] [--logging]
                              [--help]

    Run the hyper-shell server.

|

-------------------

|

``-o``, ``--output``   ``PATH``
    The path to write command lines which returned a non-zero exit status. If no path
    is provided, lines are printed to ``stdout``.

|

``-s``, ``--maxsize``   ``SIZE``
    Maximum size of the queue (default: 10000). To avoid the server queueing up
    too many tasks, this will force the server to block if clients have not yet
    taken enough commands. This is helpful for pipelines.

|

See the :ref:`network <network>` and :ref:`logging <logging>` pages for details
on those options.

.. toctree::
    :maxdepth: 3
    :hidden:

