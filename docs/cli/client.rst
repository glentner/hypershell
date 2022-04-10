.. _cli_client:

client
======

`Under construction` ...


.. code-block:: none

    usage: hyper-shell client [-h] [-N NUM] [-t TEMPLATE] [-b SIZE] [-w SEC] [-d SEC]
                              [-H ADDR] [-p PORT] [-k KEY] [-o PATH] [-e PATH]

    Launch client directly, run tasks in parallel.

    options:
    -N, --num-tasks   NUM   Number of tasks to run in parallel (default: 1).
    -t, --template    CMD   Command-line template pattern (default: "{}").
    -b, --bundlesize  SIZE  Bundle size for finished tasks (default: 1).
    -w, --bundlewait  SEC   Seconds to wait before flushing tasks (default: 5).
    -H, --host        ADDR  Hostname for server.
    -p, --port        NUM   Port number for server.
    -k, --auth        KEY   Cryptographic key to connect to server.
    -d, --delay-start SEC   Seconds to wait before start-up (default: 0).
    -o, --output      PATH  Redirect task output (default: <stdout>).
    -e, --errors      PATH  Redirect task errors (default: <stderr>).
    -c, --capture           Capture individual task <stdout> and <stderr>.
    -h, --help              Show this message and exit.

