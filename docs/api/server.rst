.. _mod_server:

:mod:`hypershell.server`
========================

.. module:: hypershell.server
    :platform: Unix, Windows

`Under construction` ...


Directly create a server instance from an iterable of tasks (strings).

-------------------

|

.. autofunction:: serve_from

    .. note::

        Something important to remember.

    Example:
        >>> from hypershell.server import serve_from
        >>> serve_from(['echo AA', 'echo BB', 'echo CC'])
