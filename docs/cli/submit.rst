.. _cli_submit:

submit
======

`Under construction` ...


.. code-block:: none

    usage: hyper-shell submit [-h] [FILE] [-b NUM] [-w SEC] [-t CMD]
    Submit tasks from a file.

    arguments:
    FILE                   Path to task file ("-" for <stdin>).

    options:
    -t, --template    CMD  Submit-time template expansion (default: "{}").
    -b, --bundlesize  NUM  Number of lines to buffer (default: 1).
    -w, --bundlewait  SEC  Seconds to wait before flushing tasks (default: 5).
    -h, --help             Show this message and exit.
