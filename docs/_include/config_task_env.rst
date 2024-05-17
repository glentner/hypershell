A few common environment variables are defined for every task.

|

``TASK_ID``
    Universal identifier (UUID) for the current task.

``TASK_ARGS``
    Original input command-line argument line.
    Equivalent to ``{}``, see :ref:`templates <templates>` section.

``TASK_SUBMIT_ID``
    Universal identifier (UUID) for *submitting* application instance.

``TASK_SUBMIT_HOST``
    Hostname of *submitting* application instance.

``TASK_SUBMIT_TIME``
    Timestamp task was submitted.

``TASK_SERVER_ID``
    Universal identifier (UUID) for *server* application instance.

``TASK_SERVER_HOST``
    Hostname of *server* application instance.

``TASK_SCHEDULE_TIME``
    Timestamp task was scheduled by server.

``TASK_CLIENT_ID``
    Universal identifier (UUID) for *client* application instance.

``TASK_CLIENT_HOST``
    Hostname of *client* application instance.

``TASK_COMMAND``
    Final command line for task.

``TASK_ATTEMPT``
    Integer number of attempts for current task (starts at 1).

``TASK_PREVIOUS_ID``
    Universal identifier (UUID) for previous attempt (if any).

``TASK_CWD``
    Current working directory for the current task.

``TASK_START_TIME``
    Timestamp task began execution.

``TASK_WAITED``
    Time in seconds between task submit time and schedule time.

``TASK_OUTPATH``
    Absolute file path where standard output is directed (if defined).

``TASK_ERRPATH``
    Absolute file path where standard error is directed (if defined).

|

Further, any environment variable starting with ``HYPERSHELL_EXPORT_`` will be injected
into the task environment sans prefix; e.g., ``HYPERSHELL_EXPORT_FOO`` would define
``FOO`` in the task environment. You can also define such variables in the ``export``
section of your configuration file(s); e.g.,


.. admonition:: ~/.hypershell/config.toml
    :class: note

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
