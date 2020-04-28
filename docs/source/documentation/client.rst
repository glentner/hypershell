Client Usage
============

The *client* connects to the server and pulls commands off one at a time,
executing them on the local shell. The shell and environment inherit from the
client's execution environment.

The output of commands are simply redirected to ``stdout`` unless otherwise
specified by ``--output``. To isolate output from individual commands, you can
specify how to redirect from inside the command template; e.g.,

.. code-block:: bash

    ➜ hyper-shell client -t '{} >$TASK_ID.out'

|

With no arguments, the client will just print a usage statement and exit.

.. code-block::

    ➜ hyper-shell client
    usage: hyper-shell client [--host ADDR] [--port PORT] [--authkey KEY] [--timeout SEC]
                              [--template CMD] [--output FILE]
                              [--verbose | --debug] [--logging]
                              [--help]

    Run the hyper-shell client.

|

To prompt the client to run with all default arguments a double dash, ``--``, is
interpreted as a simple noarg.

.. code-block::

    ➜ hyper-shell client --

|

-------------------

|

``-x``, ``--timeout``   ``SEC``
    Length of time in seconds before disconnecting (default: 0). If finished
    with the previous command and no other commands are published by the server
    after this period of time, automatically disconnect and shutdown. A
    timeout of 0 is special and means never timeout.

    To automatically disconnect and shutdown after 10 minutes without tasks:

    .. code-block::

        ➜ hyper-shell client -x600

|

``-t``, ``--template`` ``CMD``
    Template command (default: "{}"). Any valid command can be a template.
    All "{}" are substituted (if present) as the input task argument.
    This is useful if piping arguments in from another command or location
    and the command is the same in all cases but for the input argument.

    To process the incoming tasks as arguments to be called against some
    script, ``my_code``, and isolate output by tasks:

    .. code-block:: bash

        ➜ hyper-shell client -t 'my_code {} >outputs/{}.out'

|

``-o``, ``--output``   ``PATH``
    The path to write command outputs. If no path is provided, lines are printed
    to ``stdout``.

    Instead of using a shell redirect, write outputs to an explicitly named
    file path, ``outputs.txt``:

    .. code-block::

        ➜ hyper-shell client -o outputs.txt

|

See the :ref:`network <network>` and :ref:`logging <logging>` pages for details
on those options.

.. toctree::
    :maxdepth: 3
    :hidden:
