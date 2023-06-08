Submit tasks from a file.

Tasks are accumulated and published in bundles to the database.
The ``-b``/``--bundlesize`` and ``-w``/``--bundlewait`` options control the
size of these bundles and how long to wait before flushing tasks regardless of
how many have accumulated.

Pre-format tasks at `submit`-time with template expansion using ``-t``/``--template``.
Any tags specified with ``--tag`` are applied to all tasks submitted.
