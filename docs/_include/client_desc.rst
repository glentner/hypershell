Launch client directly, run tasks in parallel.

The client connects to the server and pulls bundles of tasks off the shared queue.
These tasks are run locally by some number of a parallel task executors.

The environment for tasks are the same as for the client. Standard output and error
for tasks are forwarded to that of the client, unless ``--capture`` is used, in which
these are directed to individual files for each task.
