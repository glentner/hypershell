A few common environment variables are defined for every task.

``TASK_ID``
    Universal identifier (UUID) for the current task.

``TASK_ARGS``
    Original input command-line argument line.
    Equivalent to ``{}``, see :ref:`templates <templates>` section.

``TASK_CWD``
    Current working directory for the current task.

``TASK_OUTPATH``
    Absolute file path where standard output is directed (if defined).

``TASK_ERRPATH``
    Absolute file path where standard error is directed (if defined).

Further, any environment variable starting with ``HYPERSHELL_EXPORT_`` will be injected
into the task environment sans prefix; e.g., ``HYPERSHELL_EXPORT_FOO`` would define
``FOO`` in the task environment. You can also define such variables in the ``export``
section of your configuration file(s); e.g.,

.. code-block:: toml

    # File automatically created on 2022-07-02 11:57:29.332993
    # Settings here are merged automatically with defaults and environment variables

    [logging]
    level = "info"

    # Options defined as a list will be joined with a ":" on BSD/Linux or ";" on Windows
    # Environment variables will be in all-caps (e.g., FOO and PATH).
    [export]
    foo = "value"
    path = ["/some/bin", "/some/other/bin"]
