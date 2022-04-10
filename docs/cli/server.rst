.. _cli_server:

server
======

`Under construction` ...


.. code-block:: none

    usage: hyper-shell server [-h] [FILE | --forever | --restart] [-b NUM] [-w SEC] [-r NUM [--eager]]
                              [-H ADDR] [-p PORT] [-k KEY] [--no-db] [--print | -f PATH]

    Launch server, schedule directly or asynchronously from database.

    The server includes a scheduler component that pulls tasks from the database and offers
    them up on a distributed queue to clients. It also has a receiver that collects the results
    of finished tasks. Optionally, the server can submit tasks (FILE). When submitting tasks,
    the -w/--bundlewait and -b/bundlesize options are the same as for 'hypershell submit'.

    With --max-retries greater than zero, the scheduler will check for a non-zero exit status
    for tasks and re-submit them if their previous number of attempts is less.

    Tasks are bundled and clients pull them in these bundles. However, by default the bundle size
    is one, meaning that at small scales there is greater responsiveness.

    arguments:
    FILE                        Path to task file ("-" for <stdin>).

    options:
    -H, --bind            ADDR  Bind address (default: localhost).
    -p, --port            NUM   Port number (default: 50001).
    -k, --auth            KEY   Cryptographic key to secure server.
        --forever               Do not halt even if all tasks finished.
        --restart               Restart scheduling from last completed task.
    -b, --bundlesize      NUM   Size of task bundle (default: 1).
    -t, --bundlewait      SEC   Seconds to wait before flushing tasks (with FILE, default: 5).
    -r, --max-retries     NUM   Auto-retry failed tasks (default: 0).
        --eager                 Schedule failed tasks before new tasks.
        --no-db                 Run server without database.
        --restart               Include previously failed or interrupted tasks.
        --print                 Print failed task args to <stdout>.
    -f, --failures        PATH  File path to redirect failed task args.
    -h, --help                  Show this message and exit.

