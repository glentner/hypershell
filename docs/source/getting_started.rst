.. _getting_started:

Getting Started
===============


Installation
------------

*Hyper-Shell* is built on Python 3.7+ and can be installed using Pip.

.. code-block::

    ➜ pip install hyper-shell

See the section on :ref:`Advanced Installation <advanced_install>` for
additional notes and some recommendations.

|

Basic Usage
-----------

Complete details on all execution modes, parallelism, and options are
available in the :ref:`documentation <documentation>` section.
Complete, specific examples are also available in the
:ref:`tutorials <tutorials>` section.

In most cases, using the *cluster* subcommand is best. If you have some
file, ``TASKFILE``, that lists shell commands that you might otherwise
execute alone (which would run each line in serial), pass that file
to *hyper-shell* to process those commands in parallel.

.. code-block::

    ➜ hyper-shell cluster TASKFILE

To specify the number of tasks to execute simultaneously, use ``--num-cores``
(or ``-N`` for short).

.. code-block::

    ➜ hyper-shell cluster TASKFILE -N16

Assuming the individual commands run on a single-core (they themselves are
not parallel applications), you should use the same number as the number
of cores on your system (*hyper-shell* does this automatically for you if
left unspecified).

Some commands may fail for whatever reason. To track which input commands
had a non-zero exit status, specify the ``--failed`` (or ``-f`` for short)
option. This output file will contain lines from the input file that failed.

.. code-block::

    ➜ hyper-shell cluster TASKFILE -N16 -f TASKFILE.failed


.. toctree::
    :maxdepth: 3
    :hidden:
