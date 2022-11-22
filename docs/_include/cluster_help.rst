Arguments
^^^^^^^^^

FILE
    Path to input task file (default: <stdin>).

Modes
^^^^^

``--ssh`` *HOST*...
    Launch directly with SSH host(s). This can be a single host, a comma-separated list of hosts,
    or an expandable pattern, e.g., "cluster-a[00-04].xyz".

    See also ``--ssh-group`` and ``--ssh-args``.

``--mpi``
    Same as ``--launcher=mpirun``.

``--launcher`` *ARGS*...
    Use specific launch interface. This can be any program that handles process management on a
    distributed system. For example, on a *SLURM* cluster one might want to use ``srun``. In this
    case you would specify ``--launcher=srun``; however, the *ARGS* are not merely the executable
    but the full listing, e.g., ``--launcher='srun --mpi=pmi2'``.

Options
^^^^^^^

``-N``, ``--num-tasks`` *NUM*
    Number of task executors per client (default: 1).

    For example, ``-N4`` would create four workers, but ``-N4 --ssh 'cluster-a[00-01].xyz'``
    creates two clients and a total of eight workers.

``-t``, ``--template`` *CMD*
    Command-line template pattern (default: "{}").

    This is expanded by the client just before execution. With the default "{}" the input
    command-line will be run verbatim. Specifying a template pattern allows for simple input
    arguments (e.g., file paths) to be transformed into some common form; such as
    ``-t './some_command.py {} >outputs/{/-}.out'``.

    See section on `templates`.

``-p``, ``--port`` *NUM*
    Port number (default: 50001).

    This is an arbitrary choice and simply must be an available port. The default option chosen
    here is typically available on most platforms and is not expected by any known major software.

``-b``, ``--bundlesize`` *SIZE*
    Size of task bundle (default: 1).

    The default value allows for greater concurrency and responsiveness on small scales. This is
    used by the `submit` thread to accumulate bundles for either database commits and/or publishing
    to the queue. If a database is in use, the scheduler thread selects tasks from the database in
    batches of this size.

    Using larger bundles is a good idea for large distributed workflows; specifically, it is best
    to coordinate bundle size with the number of executors in use by each client.

    See also ``--num-tasks`` and ``--bundlewait``.

``-w``, ``--bundlewait`` *SEC*
    Seconds to wait before flushing tasks (default: 5).

    This is used by both the `submit` thread and forwarded to each `client`. The `client` collector
    thread that accumulates finished task bundles to return to the `server` will push out a bundle
    after this period of time regardless of whether it has reached the preferred bundle size.

    See also ``--bundlesize``.

``-r``, ``--max-retries`` *NUM*
    Auto-retry failed tasks (default: 0).

    If a database is in use, then there is an opportunity to automatically retry failed tasks. A
    task is considered to have failed if it has a non-zero exit status. Setting this value greater
    than zero defines the number of attempts for the task. The original is not over-written, a new
    task is submitted and later scheduled.

    See also ``--eager``.

``--eager``
    Schedule failed tasks before new tasks. If ``--max-retries`` is greater than one, this option
    defines the appetite for re-submitting failed tasks. By default, failed tasks will only be
    scheduled when there are no more remaining novel tasks.

``--no-db``
    Disable database (submit directly to clients).

    By default, a scheduler thread selects tasks from a database that were previously submitted.
    With ``--no-db`` enabled, there is no scheduler and instead the `submit` thread publishes
    bundles directly to the queue.

``--initdb``
    Auto-initialize database.

    If a database is configured for use with the workflow (e.g., PostgreSQL), auto-initialize
    tables if they don't already exist. This is a short-hand for pre-creating tables with the
    ``hyper-shell initdb`` command. This happens by default with SQLite databases.

    Mutually exclusive to ``--no-db``. See ``hyper-shell initdb`` command.

``--no-confirm``
    Disable client confirmation of task bundle received.

    To achieve even higher throughput at large scales, optionally disable confirmation
    payloads from clients. Consider using this option when also using ``--no-db``.

``--forever``
    Schedule forever.

    Typically, the `cluster` will process some finite set of submitted tasks. When there are
    no more tasks left to schedule, the `cluster` will begin its shutdown procedure. With
    ``--forever`` enabled, the scheduler will continue to wait for new tasks indefinitely.

    Conflicts with ``--no-db`` and mutually exclusive to ``--restart``.

``--restart``
    Start scheduling from last completed task.

    Instead of pulling a new list of tasks from some input `FILE`, with ``--restart`` enabled the
    `cluster` will restart scheduling tasks where it left off. Any task in the database that was
    previously scheduled but not completed will be reverted.

    For very large workflows, an effective strategy is to first use the ``submit`` workflow to
    populate the database, and then to use ``--restart`` so that if the `cluster` is interrupted,
    it can easily continue where it left off, halting if nothing to be done.

    Conflicts with ``--no-db`` and mutually exclusive to ``--forever``.

``--ssh-args`` *ARGS*...
    Command-line arguments for SSH. For example, ``--ssh-args '-i ~/.ssh/my_key'``.

``--ssh-group`` *NAME*
    SSH nodelist group in config.

    In your configuration under ``[ssh.nodelist]`` can be one or more named lists. These lists
    should contain host names to associate with the group name.

    See `configuration` section.

``-E``, ``--env``
    Send environment variables. Only for ``--ssh`` mode, all ``HYPERSHELL_`` prefixed environment
    variables can be exported to the remote clients.

``-d``, ``--delay-start`` *SEC*
    Delay time in seconds for launching clients (default: 0).

    At larger scales it can be advantageous to uniformly delay the client launch sequence.
    Hundreds or thousands of clients connecting to the server all at once is a challenge.
    Even if the server could handle the load, your task throughput would be unbalanced,
    coming in waves.

    Use ``--delay-start`` with a negative number to impose a uniform random delay up to the
    magnitude specified (e.g., ``--delay-start=-600`` would delay the client up to ten minutes).
    This also has the effect of staggering the workload. If your tasks take on the order of 30
    minutes and you have 1000 nodes, choose ``--delay-start=-1800``.

``-c``, ``--capture``
    Capture individual task <stdout> and <stderr>.

    By default, the `stdout` and `stderr` streams of all tasks are fused with that of the `client`
    thread, and in turn the `cluster`. If tasks are producing output that needs to be isolated, the
    tasks need to manage their own output, you can specify a redirect as part of a ``--template``,
    or use ``--capture`` to capture these as ``.out`` and ``.err`` files.

    These are stored local to the `client`. Task outputs can be automatically retrieved via SFTP,
    see *task* usage.

``-o``, ``--output`` *PATH*
    File path for task outputs (default: <stdout>).

    If local only (not ``--ssh``, ``--mpi`` or ``--launcher``), then the *client* can redirect all
    *stdout* from tasks to some file *PATH* together.

``-e``, ``--errors`` *PATH*
    File path for task errors (default: <stderr>).

    If local only (not ``--ssh``, ``--mpi`` or ``--launcher``), then the *client* can redirect all
    *stderr* from tasks to some file *PATH* together.

``-f``, ``--failures`` *PATH*
    File path to write failed task args (default: <none>).

    The *server* acts like a sieve, reading task args from *stdin* and redirecting those original
    args to *stdout* if the task had a non-zero exit status. The *cluster* will run the *server*
    for you and if ``--failures`` is enabled these task args will be sent to a local file *PATH*.
