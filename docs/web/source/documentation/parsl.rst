.. _parsl_doc:

Parsl Mode
==========

Visit `parsl-project.org <https://parsl-project.org>`_ for information regarding
the *Parsl* project. Complete documentation on the library is available at
`parsl.readthedocs.io <https://parsl.readthedocs.io>`_.

*Hyper-Shell* can use *Parsl* as a scheduler to execute shell commands and
handle all of the scaling. Any valid *Parsl* configuration should work for
this purpose. See the complete section on
`configuration <https://parsl.readthedocs.io/en/stable/userguide/configuring.html>`_.

Initially, *hyper-shell* will lay down a default configuration file at
``~/.hyper-shell/parsl_config.py``:

.. code-block:: python

    # Hyper-shell Parsl configuration file.

    # Import and create configuration objects via Parsl.
    # Hyper-shell will import this module and inspect for Python
    # objects by name that have type `parsl.config.Config`.

    # default configuration, do not remove this line
    from parsl.configs.local_threads import config as local

As stated in the comments, this module file is executed and any `Config`
object defined therein is exported with it's locally defined name. That
name can be invoked from the command line using the ``--profile`` option.

Initially, ``local`` is the default parsl configuration which simply uses
local threads to execute tasks.

|
|

.. image:: https://www.cray.com/sites/default/files/images/Solutions_Images/bluewaters.png
    :target: https://parsl.readthedocs.io/en/stable/userguide/configuring.html#blue-waters-cray
    :alt: Blue Waters

|

From *parsl*'s documentation on configuring for an HPC system, below is
a reproduction of a working config for the *Blue Waters* system, a
flagship system at the National Center for Supercomputing Applications.

|

.. code-block:: python

    # Hyper-shell Parsl configuration file.

    # Import and create configuration objects via Parsl.
    # Hyper-shell will import this module and inspect for Python
    # objects by name that have type `parsl.config.Config`.

    # default configuration, do not remove this line
    from parsl.configs.local_threads import config as local

    from parsl.config import Config
    from parsl.executors import HighThroughputExecutor
    from parsl.addresses import address_by_hostname
    from parsl.launchers import AprunLauncher
    from parsl.providers import TorqueProvider


    bigblue = Config(
        executors=[
            HighThroughputExecutor(
                label="bw_htex",
                cores_per_worker=1,
                worker_debug=False,
                address=address_by_hostname(),
                provider=TorqueProvider(
                    queue='normal',
                    launcher=AprunLauncher(overrides="-b -- bwpy-environ --"),
                    scheduler_options='',  # string to prepend to #SBATCH blocks in the submit script to the scheduler
                    worker_init='',  # command to run before starting a worker, such as 'source activate env'
                    init_blocks=1,
                    max_blocks=1,
                    min_blocks=1,
                    nodes_per_block=2,
                    walltime='00:10:00'
                ),
            )

        ],

    )


.. toctree::
    :maxdepth: 3
    :hidden:
