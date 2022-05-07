Launch server, schedule directly or asynchronously from database.

The server includes a scheduler component that pulls tasks from the database and offers
them up on a distributed queue to clients. It also has a receiver that collects the results
of finished tasks. Optionally, the server can submit tasks (*FILE*). When submitting tasks,
the ``-w``/``--bundlewait`` and ``-b``/``bundlesize`` options are the same as for
*submit* workflow.

With ``--max-retries`` greater than zero, the scheduler will check for a non-zero exit status
for tasks and re-submit them if their previous number of attempts is less.

Tasks are bundled and clients pull them in these bundles. However, by default the bundle size
is one, meaning that at small scales there is greater concurrency.
