.. _advanced_install:

Advanced
========


Advanced Installation
---------------------

The program itself can be installed anywhere and doesn't care how it's invoked.
When launching clients with ``--ssh`` or similar, a compatible version of *hyper-shell*
must exist on the destination host.

Take care when installing *hyper-shell* inside a container such as *Singularity* or
*Docker*. Libraries (e.g., *MPI*) will need to be compatible inside the container and
outside the container.

The *Parsl* library can be tricky to make happy in some contexts because it wants to
launch it's own commands and on a shared HPC-like system you must take care to expose the
*Parsl* installation to itself.

On a shared system, it is recommended to isolate *hyper-shell* from other users' Python
environments by installing into a *virtual* or *Anaconda* environment, lifting only the
binaries out (and maybe specific libraries).

Example:

.. code-block::

    .
    ├── bin/
    │   └── hyper-shell -> ../build/bin/hyper-shell*
    ├── build/
    │   ├── bin/...
    │   ├── lib/...
    │   ...
    ├── man -> source/man/
    ├── modulefiles/
    │   └── hyper-shell/[VERSION].lau
    └── source/
        ├── ...
        └── setup.py

The *build* directory is a *Miniconda* environment with the hyper-shell *source*
repository installed *into* it. The constructed executable is lifted out without
polluting the users' PATH. The *LMOD* module specification file exposed only a
minimal PATH and MANPATH extension.

Additional steps may be necessary to make Parsl available to a remote *hyper-shell*
and depend on the requirements of the system.



.. toctree::
    :maxdepth: 3
    :hidden:
