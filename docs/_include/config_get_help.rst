Arguments
^^^^^^^^^

`SECTION[...].VAR`
    Path to variable (default is entire configuration).

Options
^^^^^^^

``--system``
    Load from system configuration.

``--user``
    Load from user configuration.

``--local``
    Load from local configuration.

``--default``
    Load from default configuration.

``-x``, ``--expand``
    Expand variable.

    If the special ``_env`` or ``_eval`` variant of the option is
    present in the configuration, it will expand the environment variable
    or shell command, respectively.

``-r``, ``--raw``
    Disable formatting on single value output.
