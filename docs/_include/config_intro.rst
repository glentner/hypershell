Most of the choices that `HyperShell` makes about timing, task bundling, coordination, logging,
and such are configurable by the user. This configuration is loaded when the program starts
and is constructed from several sources including an ordered merger of files, environment variables,
and command-line options.

In order of precedence (lowest to highest), three files are loaded for `system`, `user` and `local`
configuration. See below the section on file system paths for more details.

On Linux (for example):

.. table::
    :widths: 30 70

    ================  =================================
    Site              Path (Linux / POSIX)
    ================  =================================
    System            ``/etc/hypershell.toml``
    User              ``~/.hypershell/config.toml``
    Local             ``./.hypershell/config.toml``
    ================  =================================


The `TOML <https://toml.io>`_ format is modern and minimal.

Every configurable option can be set in one of these files. Further, every option can
also be set by an environment variable, where the name aligns to the path
to that option, delimited by underscores.

For example, set the logging level at the user level with a command:

.. admonition:: Set user-level configuration option
    :class: note

    .. code-block:: shell

        hs config set logging.level info --user

The file should now look something like this:

.. admonition:: ~/.hypershell/config.toml
    :class: note

    .. code-block:: toml

        # File automatically created on 2022-07-02 11:57:29.332993
        # Settings here are merged automatically with defaults and environment variables

        [logging]
        level = "info"

Alternatively, you can set an environment variable and the runtime configuration
would be equivalent:

.. admonition:: Define environment variable
    :class: note

    .. code-block:: shell

        export HYPERSHELL_LOGGING_LEVEL=INFO

Finally, any option defined within a configuration file that ends with ``_env`` or ``_eval``
is automatically expanded by the given environment variable or shell expression,
respectively. This is useful as both a dynamic feature but also as a means to
obfuscate sensitive information, such as database connection details.

.. admonition:: ~/.hypershell/config.toml
    :class: note

    .. code-block:: toml

        # File automatically created on 2022-07-02 11:57:29.332993
        # Settings here are merged automatically with defaults and environment variables

        [logging]
        level = "info"

        [database]
        provider = "postgres"
        database = "hypershell"
        host = "my.instance.university.edu"
        user = "me"
        password_eval = "pass hypershell/database/password"  # Decrypt using GNU Pass
