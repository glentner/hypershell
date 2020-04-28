.. _network:

Network Options
===============

When using the high level *cluster* mode no networking options are necessary.
In essence, the *server* is managing a shared queue over a *port*. By default,
*hyper-shell* uses port 50001. This is an arbitrary choice and any other port
number may be used, provided it's allowed by the system.

When clients connect to the server instance, they are required to provide a
unique authorization key. This key can be any valid, continuous string of
numbers and letters. No specific requirement exists on length or quality.
A default authorization key is defined (as ``--BADKEY--``) for simplicity
and ease of use in otherwise secure environments.

A secure authorization key is automatically generated and used
for the clients when executing in *cluster* mode.

|

-------------------

|

``-H``, ``--host``   ``ADDR``
    The hostname or IP address to use. For the *server* this is the bind
    address (default: ``localhost``). This can be changed to allow for
    remote connections (e.g., ``0.0.0.0``). Clients will need to provide
    a hostname or IP address if not on the same machine.

    Start the server and set the bind address to allow for remote clients:

    .. code-block:: none

        ➜ hyper-shell server -H 0.0.0.0

    Connect to the server running at ``host-1``:

    .. code-block:: none

        ➜ hyper-shell client -H host-1

|

``-p``, ``--port``   ``PORT``
    The port number for the server (default: 50001). The port number is an
    arbitrary choice and just needs to be allowed by the system (i.e., not
    blocked or reserved).

    Specify a particular port number when starting the server:

    .. code-block:: none

        ➜ hyper-shell server -H 0.0.0.0 -p 54321

    Connect to the server:

    .. code-block:: none

        ➜ hyper-shell client -H host-1 -p 54321

|

``-k``, ``--authkey``   ``KEY``
    Cryptographic authorization key for client connections (default: ``--BADKEY--``).
    This is set by the *server* and required for a *client* to connect.
    The default is intentionally meant to suggest you set something more appropriate.
    In *cluster* mode, a secure key is automatically generated if none is
    explicitly provided.

    Use a particular authorization key for the server instance:

    .. code-block:: none

        ➜ hyper-shell server -H 0.0.0.0 -k MY_SPECIAL_KEY

    Connect to the server using the key:

    .. code-block:: none

        ➜ hyper-shell client -H host-1 -k MY_SPECIAL_KEY


.. toctree::
    :maxdepth: 3
    :hidden:
