Environment Variables
=====================

Currently, there is no real configuration file (apart from ``parsl``). However,
*hyper-shell*'s behavior is effected by any number of environment variables.

There are a few variables that are defined *by* hyper-shell. These are set
individually for each task and consist of the unique information for that task.
These variables are available within the body of a command line.

|

``TASK_ID``
    The unique integer identifier for this task. The value of ``TASK_ID`` is
    a count starting from zero set by the server.

|

``TASK_ARG``
    The input argument for this command. This is the variable equivalent of '{}'
    and can be substituted as such. This may be useful for shell-isms in
    the command template.

    Strip the filename extension from incoming file paths:

    .. code-block:: bash

        ➜ hyper-shell client -t 'my_code ${TASK_ARG%.*}'

|

-------------------

|

There are a few environment variables that *you* can define that affect
*hyper-shell*'s behavior.

|

``HYPERSHELL_EXE``
    When running the cluster with ``--ssh`` (or similar) it is
    not uncommon for hyper-shell on the remote system to either be in a
    different location or not necessarily available on the *PATH*. Using the
    ``HYPERSHELL_EXE`` environment variable, set an explicit path to use.

    .. code-block:: bash

        export HYPERSHELL_EXE=/other/bin/hyper-shell

|

``HYPERSHELL_CWD``
    When executed directly, the hyper-shell client will run tasks in the same
    directory as the client is running in. This can be changed by specifying the
    ``HYPERSHELL_CWD``.

    .. code-block:: bash

        export HYPERSHELL_CWD=$HOME/other

|

``HYPERSHELL_LOGGING_LEVEL``
    You can specify what logging level to use without the need for a command line
    switch by defining this variable. Both numbered and named values are allowed;
    e.g., 0-4 or one of DEBUG, INFO, WARNING, ERROR, and CRITICAL.

    .. code-block:: bash

        $ export HYPERSHELL_LOGGING_LEVEL=DEBUG

|

``HYPERSHELL_LOGGING_HANDLER``
    You can specify what logging style to use without the need for a command line
    switch by defining this variable. Allowed values are STANDARD or DETAILED,
    corresponding to the basic colorized messages and the syslog style detailed
    messages, respectively.

    .. code-block:: bash

        $ export HYPERSHELL_LOGGING_HANDLER=DETAILED

-------------------

|

Finally, all environment variables that start with the ``HYPERSHELL_`` prefix
will be injected into the execution environment of the tasks with the prefix
stripped.

Example:

.. code-block:: bash

    export HYPERSHELL_PATH=/other/bin:$PATH
    export HYPERSHELL_OTHER=FOO

All tasks will have ``PATH=/other/bin:$PATH`` defined for the task as well
as a new variable, ``OTHER=foo``.


.. note::

    If running in *cluster* mode, the clients may or may not inherit these
    variables. The ``--mpi`` mode might export your variables to the remote
    environment for you.


.. toctree::
    :maxdepth: 3
    :hidden:
