.. _logging:

Logging Options
===============

All logging messages are written to ``stderr`` to allow for command outputs
to occupy ``stdout``. *Hyper-Shell* follows a standard arrangement for its
logging messages with five *levels*; ``DEBUG``, ``INFO``, ``WARNING``,
``ERROR``, and ``CRITICAL``. Setting a particular logging level means that
messages *below* that level are suppressed.

By default, the logging level is set to ``WARNING``, as such, no messages will
be printed unless there is some kind of issue (e.g., a non-zero exit status for
a given task). To show informational messages (e.g., a task was queued, executed,
or completed), use ``--verbose``. To show debugging messages (e.g., clients
connecting or disconnecting) use ``--debug``.

There are two modes of logging in addition to these distinct levels. The normal
mode is intended for interactive use and is colorized according to the level of
the message. There is also a *syslog* style of messaging, configurable with the
``--logging`` option which disables colors and shows additional metadata such as
the hostname and a timestamp. This is important when running in a long, detached
context such as a pipeline or job.


Logging messages are colored according to their severity; blue,
green, yellow, red, and purple for debug, info, warning, error, and critical,
respectively. A non-zero exit status by a task is considered a warning, not
an error. A critical message is reserved for situations in which *hyper-shell*
cannot continue to run.

|

``-v``, ``--verbose``
    Include information level messages. (conflicts with ``--debug``).

|

``-d``, ``--debug``
    Include debugging level messages. (conflicts with ``--verbose``).

|

``-l``, ``--logging``
    Show detailed syslog style messages. This disables colorized output and
    alters the format of messages to include a timestamp, hostname, and the
    level name.



.. toctree::
    :maxdepth: 3
    :hidden:
