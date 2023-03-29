Arguments
^^^^^^^^^

FIELD
    Select specific named fields to include in output.
    Default is to include all fields.

Options
^^^^^^^

``-w``, ``--where`` *COND...*
    List of conditional statements to filter results (e.g., ``-w 'exit_status != 0'``).

``-s``, ``--order-by`` *FIELD*
    Order results by field.

``-x``, ``--extract``
    Disable formatting for single column output.

``--failed``
    Alias for ``-w 'exit_status != 0'``.

``--succeeded``
    Alias for ``-w 'exit_status == 0'``.

``--finished``
    Alias for ``-w 'exit_status != null'``.

``--remaining``
    Alias for ``-w 'exit_status == null'``.

``--json``
    Format output as JSON.

``--csv``
    Format output as CSV.

``-l``, ``--limit`` *NUM*
    Limit number of returned results.

``-c``, ``--count``
    Only print number of results that would be returned.
