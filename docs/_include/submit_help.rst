Arguments
^^^^^^^^^

FILE
    Path to input task file (default: <stdin>).

Options
^^^^^^^

``-t``, ``--template`` *CMD*
    Command-line template pattern (default: "{}").

    This is expanded at submit-time before sending to the database.
    With the default "{}" the input command-line will be run verbatim.
    Specifying a template pattern allows for simple input arguments (e.g., file paths)
    to be transformed into some common form; such as
    ``-t './some_command.py {} >outputs/{/-}.out'``.

    See section on `templates`.

``-b``, ``--bundlesize`` *SIZE*
    Size of task bundle (default: 1).

    The default value allows for greater concurrency and responsiveness on small scales.
    Using larger bundles is a good idea for large distributed workflows; specifically, it is best
    to coordinate bundle size with the number of executors in use by each client.

    See also ``--bundlewait``.

``-w``, ``--bundlewait`` *SEC*
    Seconds to wait before flushing tasks (default: 5).

    If this period of time expires since the previous bundle was pushed to the database,
    The current bundle will be pushed regardless of how many tasks have been accumulated.

    See also ``--bundlesize``.

``--initdb``
    Auto-initialize database.

    If a database is configured for use with the workflow (e.g., PostgreSQL), auto-initialize
    tables if they don't already exist. This is a short-hand for pre-creating tables with the
    ``hyper-shell initdb`` command. This happens by default with SQLite databases.

    See ``hyper-shell initdb`` command.
