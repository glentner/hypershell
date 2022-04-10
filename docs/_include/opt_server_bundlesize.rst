-b, --bundlesize *NUM*
    Size of task bundle (default: 1).
    When scheduling the server will select this many tasks from the database
    to bundle (though less may occur if not this many are available).
    The *submit* thread will publish tasks in batches of this size;
    without a database, this will be the bundle size.

    See also, ``--bundlewait``.
    Set configuration value ``server.bundlesize`` or environment variable
    ``HYPERSHELL_SERVER_BUNDLESIZE``.
