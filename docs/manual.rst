Manual Page
===========

Synopsis
--------

| hyper-shell client  [-h] [*args*...]
| hyper-shell server  [-h] *TASKFILE* [*args*...]
| hyper-shell submit  [-h] *TASKFILE* [*args*...]
| hyper-shell cluster [-h] *TASKFILE* [*args*...]


Description
-----------

The ``hyper-shell`` utility is a cross-platform, high performance computing
utility for processing arbitrary shell commands over a distributed, asynchronous
queue.

Command-Line Usage
------------------

hyper-shell cluster
^^^^^^^^^^^^^^^^^^^

hyper-shell server
^^^^^^^^^^^^^^^^^^

hyper-shell client
^^^^^^^^^^^^^^^^^^

hyper-shell submit
^^^^^^^^^^^^^^^^^^

hyper-shell config
^^^^^^^^^^^^^^^^^^

hyper-shell task search
^^^^^^^^^^^^^^^^^^^^^^^

hyper-shell task submit
^^^^^^^^^^^^^^^^^^^^^^^

hyper-shell task wait
^^^^^^^^^^^^^^^^^^^^^

hyper-shell task run
^^^^^^^^^^^^^^^^^^^^

Templates
---------

Configuration
-------------

Environment Variables
---------------------

All environment variables that start with the ``HYPERSHELL_`` prefix will be
injected into the execution environment of the tasks with the prefix stripped.


Examples
--------


See Also
--------

ssh(1), mpirun(1)
