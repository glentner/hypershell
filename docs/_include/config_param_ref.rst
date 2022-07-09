``[logging]``
    Logging configuration. See also :ref:`logging <logging>` section.

    ``.level``
        One of ``DEVEL``, ``TRACE``, ``DEBUG``, ``INFO``, ``WARNING``,
        ``ERROR``, or ``CRITICAL`` (default: `WARNING`)

    ``.datefmt``
        Date/time format, standard codes apply (default: `'%Y-%m-%d %H:%M:%S'`)

    ``.format``
        Log message format. Default set by the `default` ``logging.style``.
        See the `available attributes <https://docs.python.org/3/library/logging.html#logrecord-attributes>`_
        defined by the underlying Python logging interface.

    ``.style``
        Presets for ``logging.format`` which can be difficult to define correctly.
        Options are `default`, `detailed`, and `system`.


``[database]``
    Database configuration and connection details.
    See also :ref:`database <database>` section.

    ``.provider``
        Database provider (default: 'sqlite'). Supported alternatives include
        'postgres' (or compatible). Support for other providers may be considered in
        the future.

    ``.file``
        Only applicable for SQLite provider.
        SQLite does not understand any other connection detail.

    ``.database``
        Name for database. Not applicable for SQLite.

    ``.schema``
        Not applicable for all RDMS providers.
        For PostgreSQL the default schema is ``public``.
        Specifying the schema may be useful for having multiple instances within the same database.

    ``.host``
        Hostname or address of database server (default: `localhost`).

    ``.port``
        Port number to connect with database server.
        The default value depends on the provider, e.g., 5432 for PostgreSQL.

    ``.user``
        Username for databaser server account.
        If provided a ``password`` must also be provided.
        Default is the local account.

    ``.password``
        Password for database server account.
        If provided a ``user`` must also be provided.
        Default is the local account.

        See also note on ``_env`` and ``_eval``.

    ``.echo``
        Special parameter enables verbose logging of all database transactions.

    ``[connection_args]``
        Specify additional connection details for the underlying SQL dialect provider,
        e.g., ``sqlite3`` or ``psycopg2``.

    ``*``
        Any additional arguments are forwarded to the provider, e.g., ``encoding = 'utf-8'``.


``[server]``
    Section for `server` workflow parameters.

    ``.bind``
        Bind address (default: `localhost`).

        When running locally, the default is recommended. To allow remote *clients* to connect
        over the network, bind the server to *0.0.0.0*.

    ``.port``
        Port number (default: `50001`).

        This is an arbitrary choice and simply must be an available port. The default option chosen
        here is typically available on most platforms and is not expected by any known major software.

    ``.auth``
        Cryptographic authorization key to connect with server (default: `<not secure>`).

        The default *KEY* used by the server and client is not secure and only a place holder.
        It is expected that the user choose a secure *KEY*. The `cluster` automatically generates
        a secure one-time *KEY*.

    ``.queuesize``
        Maximum number of task bundles on the shared queue (default: `1`).

        This blocks the next bundle from being published by the scheduler until a client
        has taken the current prepared bundle. On smaller scales this is probably best and
        is only of modest performance impact, limiting the scheduler from getting so far ahead
        of the currently running tasks.

        On large scale workflows with many clients (e.g., 100) it may be advantageous to allow
        the scheduler to work ahead in selecting new tasks.

    ``.bundlesize``
        Size of task bundle (default: `1`).

        The default value allows for greater concurrency and responsiveness on small scales. This is
        used by the `submit` thread to accumulate bundles for either database commits and/or publishing
        to the queue. If a database is in use, the scheduler thread selects tasks from the database in
        batches of this size.

        Using larger bundles is a good idea for large distributed workflows; specifically, it is best
        to coordinate bundle size with the number of executors in use by each client.

        See also ``-b``/``--bundlesize`` command-line option.

    ``.attempts``
        Attempts for auto-retry on failed tasks (default: `1`).

        If a database is in use, then there is an opportunity to automatically retry failed tasks. A
        task is considered to have failed if it has a non-zero exit status. The original is not over-written,
        a new task is submitted and later scheduled.

        Counterpart to the ``-r``/``--max-retries`` command-line option. Setting ``--max-retries 1``
        is equivalent to setting ``.attempts`` to 2.

        See also ``.eager``.

    ``.eager``
        Schedule failed tasks before new tasks (default: `false`).

        If ``.attempts`` is greater than one, this option defines the appetite for re-submitting
        failed tasks. By default, failed tasks will only be scheduled when there are no more
        remaining novel tasks.

    ``.wait``
        Polling interval in seconds for database queries during scheduling (default: `5`).
        This waiting only occurs when no tasks are returned by the query.

    ``.evict``
        Eviction period in seconds for clients (default: `600`).

        If a client fails to register a heartbeat after this period of time it is considered
        defunct and is evicted. When there are no more tasks to schedule the server sends a
        disconnect request to all registered clients, and waits until a confirmation is
        returned for each. If a client is defunct, this will hang the shutdown process.


``[client]``
    Section for `client` workflow parameters.

    ``.bundlesize``
        Size of task bundle (default: `1`).

        The default value allows for greater concurrency and responsiveness on small scales.

        Using larger bundles is a good idea for larger distributed workflows; specifically, it is best
        to coordinate bundle size with the number of executors in use by each client. It is also a good
        idea to coordinate bundle size between the client and server so that the client returns the
        same sized bundles that it receives.

        See also ``-b``/``--bundlesize`` command-line option.

    ``.bundlewait``
        Seconds to wait before flushing task bundle (default: `5`).

        If this period of time expires since the previous bundle was returned to the server,
        the current group of finished tasks will be pushed regardless of `bundlesize`.

        For larger distributed workflows it is a good idea to make this waiting period sufficiently
        long so that most bundles are returned whole.

        See also ``-w``/``--bundlewait`` command-line option.

    ``.heartrate``
        Interval in seconds between heartbeats sent to server (default `10`).

        Even on the largest scales the default interval should be fine.


``[submit]``
    Section for `submit` workflow parameters.

    ``.bundlesize``
        Size of task bundle (default: `1`).

        The default value allows for greater concurrency and responsiveness on small scales.
        Using larger bundles is a good idea for large distributed workflows; specifically, it is best
        to coordinate bundle size with the number of executors in use by each client.

        See also ``-b``/``--bundlesize`` command-line option.

    ``.bundlewait``
        Seconds to wait before flushing tasks (default: `5`).

        If this period of time expires since the previous bundle was pushed to the database,
        the current bundle will be pushed regardless of how many tasks have been accumulated.

        See also ``-w``/``--bundlewait`` command-line option.


``[task]``
    Section for task runtime settings.

    ``.cwd``
        Explicitly set the working directory for all tasks.


``[ssh]``
    SSH configuration section.

    ``.args``
        SSH connection arguments; e.g., ``-i ~/.ssh/some.key``.
        It is preferable to configure SSH directly however, in ``~/.ssh/config``.

    ``[group]``
        Setting a `list` for the ``.group`` allows for a global list of available client hosts.
        Or, set one or more named groups and reference them by name with ``--ssh-group``.

        ``.<name> = ['host-01', 'host-02', 'host-03']``
