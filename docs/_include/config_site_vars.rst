``HYPERSHELL_SITE``
    The default site path for outputs is either the `user` or `system` site based
    on whether the program was run as root/admin. The `local` path is always the
    current working directory for the program. If this environment variable is set
    then it takes the place of the `local` site and used as the default.

``HYPERSHELL_CONFIG_FILE``
    Under normal operations the program searches all three `system`, `user`, and
    `local` sites to load the full configuration in addition to all prefixed
    environment variables. This can actually cause issues for scenarios with many
    instances of the program running on the same file system, such as an HPC
    cluster. In order to protect against unintended crashes from incidental
    configuration changes, defining this environment variable specifies the one
    and only path to a configuration file and all others will be ignored.
    Setting this to empty results in no files being loaded (an environment
    only runtime).
