.. _getting_started:

Getting Started
===============


Installation
------------

It is recommend that you install *hyper-shell* inside a virtual environment.
See the :ref:`installation <install>` guide for more options
and additional notes and recommendations.


.. tab:: pipx

    .. code-block:: shell

        pipx install hyper-shell

.. tab:: homebrew

    .. code-block:: shell

        brew tap glentner/hyper-shell
        brew install hyper-shell

|


Basic Usage
-----------

Complete details on all execution modes, parallelism, and options are
available in the :ref:`command-line <cli>` documentation.
Complete, specific examples are also available in the tutorials section.

In most cases, using the *cluster* subcommand is best. If you have some
file, ``tasks.in``, that lists shell commands that you might otherwise
execute alone (which would run each line in serial), pass that file
to *hyper-shell* to process those commands in parallel.

.. admonition:: Basic Usage
    :class: note

    .. code-block:: shell

        hyper-shell cluster tasks.in


To specify the number of tasks to execute simultaneously, use ``--num-cores``
(or ``-N`` for short).

.. admonition:: Parallel Workers
    :class: note

    .. code-block:: shell

        hyper-shell cluster tasks.in -N16


Assuming the individual commands run on a single-core (they themselves are
not parallel applications), you should use the same number as the number
of physical cores on your system.

Some commands may fail for whatever reason. To track which input commands
had a non-zero exit status, specify the ``--failed`` (or ``-f`` for short)
option. This output file will contain lines from the input file that failed.


.. admonition:: Track Failed Tasks
    :class: note

    .. code-block:: shell

        hyper-shell cluster tasks.in -N16 -f tasks.failed
