Most of the choices that `HyperShell` makes about timing, task bundling, coordination, logging,
and such are configurable by the user. This configuration is loaded when the program starts
and is constructed from several sources including an ordered merger of files, environment variables,
and command-line options.

In order of precedence (lowest to highest), three files are loaded:

================  =================================
Level             Path
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

.. code-block:: shell

    $ hs config set logging.level info --user

The file should now look something like this:

.. code-block:: toml

    # File automatically created on 2022-07-02 11:57:29.332993
    # Settings here are merged automatically with defaults and environment variables

    [logging]
    level = "info"

Alternatively, you can set an environment variable and the runtime configuration
would be equivalent:

.. code-block:: shell

    $ export HYPERSHELL_LOGGING_LEVEL=INFO

Finally, any option defined within a configuration file that ends with ``_env`` or ``_eval``
is automatically expanded by the given environment variable or shell expression,
respectively. This is useful as both a dynamic feature but also as a means to
obfuscate sensitive information, such as database connection details.

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
