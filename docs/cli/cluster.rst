.. _cli_cluster:

cluster
=======

`Under construction` ...


.. code-block:: none

    usage: hyper-shell cluster [-h] [FILE | --restart | --forever] [--no-db] [-N NUM] [-t CMD] [-b SIZE] [-w SEC]
                               [-r NUM [--eager]] [--capture | [-o PATH] [-e PATH]] [-f PATH] [--delay-start SEC]
                               [--ssh [HOST... | --ssh-group NAME] [--env] | --mpi | --launcher=ARGS...]

    Start cluster locally, over SSH, or with a custom launcher.

    arguments:
    FILE                        Path to input task file (default: <stdin>).

    modes:
    --ssh              HOST...  Launch directly with SSH host(s).
    --mpi                       Same as '--launcher=mpirun'
    --launcher         ARGS...  Use specific launch interface.

    options:
    -N, --num-tasks    NUM      Number of task executors per client (default: 1).
    -t, --template     CMD      Command-line template pattern (default: "{}").
    -p, --port         NUM      Port number (default: 50001).
    -b, --bundlesize   SIZE     Size of task bundle (default: 1).
    -w, --bundlewait   SEC      Seconds to wait before flushing tasks (default: 5).
    -r, --max-retries  NUM      Auto-retry failed tasks (default: 0).
        --eager                 Schedule failed tasks before new tasks.
        --no-db                 Disable database (submit directly to clients).
        --forever               Schedule forever.
        --restart               Start scheduling from last completed task.
        --ssh-args     ARGS     Command-line arguments for SSH.
        --ssh-group    NAME     SSH nodelist group in config.
    -E, --env                   Send environment variables.
    -d, --delay-start  SEC      Delay time for launching clients (default: 0).
    -c, --capture               Capture individual task <stdout> and <stderr>.
    -o, --output       PATH     File path for task outputs (default: <stdout>).
    -e, --errors       PATH     File path for task errors (default: <stderr>).
    -f, --failures     PATH     File path to write failed task args (default: <none>).
    -h, --help                  Show this message and exit.

