Manual Page
===========

Synopsis
--------

| hyper-shell [-h] [-v] ...

| hyper-shell cluster [-h] *FILE* [--ssh *HOST*... | --mpi | --launcher *ARGS*...] ...

| hyper-shell submit [-h] *FILE* ...

| hyper-shell server [-h] *FILE* ...

| hyper-shell client [-h] ...

| hyper-shell config [-h] {get | set | which | edit } [--user | --system] ...

| hyper-shell task [-h] {submit | info | wait | run | search} ...

Description
-----------

``hyper-shell`` is an elegant, cross-platform, high-performance computing utility for processing
shell commands over a distributed, asynchronous queue. It is a highly scalable workflow automation
tool for many-task scenarios.

Typically, ad hoc usage or batch jobs will use the ``cluster`` workflow. This automatically stands
up the ``server`` and one or more ``client`` instances on remote servers and processes the commands
from some input *FILE* until completion.

This can function as a pure in-memory queue; however, one can configure a database in-the-loop
to manage task scheduling and persistence. Stand up the ``server`` on its own and persistent
``clients`` on the nodes in the cluster, and ``submit`` tasks independently.


Cluster Usage
-------------

.. include:: _include/cluster_usage.rst

.. include:: _include/cluster_desc.rst

.. include:: _include/cluster_help.rst


Server Usage
------------

.. include:: _include/server_usage.rst

.. include:: _include/server_desc.rst

.. include:: _include/server_help.rst


Client Usage
------------

.. include:: _include/client_usage.rst

.. include:: _include/client_desc.rst

.. include:: _include/client_help.rst


Submit Usage
------------

.. include:: _include/submit_usage.rst

.. include:: _include/submit_desc.rst

.. include:: _include/submit_help.rst


Initdb Usage
------------

.. include:: _include/initdb_usage.rst

.. include:: _include/initdb_desc.rst

.. include:: _include/initdb_help.rst


Config Get Usage
----------------

.. include:: _include/config_get_usage.rst

.. include:: _include/config_get_desc.rst

.. include:: _include/config_get_help.rst


Config Set Usage
----------------

.. include:: _include/config_set_usage.rst

.. include:: _include/config_set_desc.rst

.. include:: _include/config_set_help.rst


Config Edit Usage
-----------------

.. include:: _include/config_edit_usage.rst

.. include:: _include/config_edit_desc.rst

.. include:: _include/config_edit_help.rst


Config Which Usage
------------------

.. include:: _include/config_which_usage.rst

.. include:: _include/config_which_desc.rst

.. include:: _include/config_which_help.rst


Task Submit Usage
-----------------

.. include:: _include/task_submit_usage.rst

.. include:: _include/task_submit_desc.rst

.. include:: _include/task_submit_help.rst


Task Info Usage
---------------

.. include:: _include/task_info_usage.rst

.. include:: _include/task_info_desc.rst

.. include:: _include/task_info_help.rst


Task Wait Usage
---------------

.. include:: _include/task_wait_usage.rst

.. include:: _include/task_wait_desc.rst

.. include:: _include/task_wait_help.rst


Templates
---------


Configuration
-------------


Environment Variables
---------------------

All environment variables that start with the ``HYPERSHELL_`` prefix will be
injected into the execution environment of the tasks with the prefix stripped.

``TASK_ID``

    Unique task UUID.

``TASK_ARGS``

    Original input command-line argument(s) for the current task.

Exit Status
-----------

.. include:: _include/exit_status.rst


Examples
--------


See Also
--------

ssh(1), mpirun(1)
