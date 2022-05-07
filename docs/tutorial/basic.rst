.. _tutorial_basic:

Basic
=====

`Under construction` ...

|

Process Data Files
------------------

With some user program ``bin/code.py``, invoke against each file in ``data/``
and re-direct outputs to individual files in the project directory.

.. admonition:: Process Data Files
    :class: note

    .. details:: Setup

        .. code-block:: shell

            export HYPERSHELL_DATABASE_FILE=tasks.db
            export HYPERSHELL_LOGGING_STYLE=default
            export HYPERSHELL_LOGGING_LEVEL=debug


    .. details:: Code
        :open:

        .. code-block:: shell

            find data/ -maxdepth 1 -type f -name '*.h5' |\
                hyper-shell cluster -N4 -b4 -w60 -t 'bin/code.py {} >output/{/-}.out'

    .. details:: Logs

        .. code-block:: none

            DEBUG [hypershell.server] Started
            DEBUG [hypershell.submit] Started (<stdin>)
            DEBUG [hypershell.server] Started (scheduler)
            DEBUG [hypershell.server] Started (heartbeat)
            DEBUG [hypershell.submit] Started (loader)
            DEBUG [hypershell.submit] Started (committer: database)
            DEBUG [hypershell.server] Started (receiver)
            DEBUG [hypershell.submit] Submitted 4 tasks
            DEBUG [hypershell.server] Scheduled task (06b22512-c52f-4357-9d2b-2a4ab90adcb9)
            DEBUG [hypershell.server] Scheduled task (04188efc-7c18-4e6f-a358-5982a30c5f1e)
            DEBUG [hypershell.server] Scheduled task (d2c28397-e668-4a31-b6d8-5d534226f165)
            DEBUG [hypershell.server] Scheduled task (f36aa178-96fe-498d-ba19-e068bbcba027)
            DEBUG [hypershell.submit] Submitted 4 tasks
            DEBUG [hypershell.submit] Submitted 4 tasks
            DEBUG [hypershell.submit] Done (loader)
            DEBUG [hypershell.submit] Submitted 4 tasks
            DEBUG [hypershell.submit] Submitted 4 tasks
            DEBUG [hypershell.submit] Done (committer: database)
            DEBUG [hypershell.submit] Done
            DEBUG [hypershell.client] Started (4 executors)
            DEBUG [hypershell.client] Started (scheduler)
            DEBUG [hypershell.client] Started (collector)
            DEBUG [hypershell.client] Started (heartbeat)
            DEBUG [hypershell.client] Started (executor-1)
            DEBUG [hypershell.client] Started (executor-2)
            DEBUG [hypershell.client] Started (executor-3)
            DEBUG [hypershell.client] Started (executor-4)
            DEBUG [hypershell.server] Registered client (workstation.local: bf2e14e7-7afd-4e32-832f-dddddb405a31)
            DEBUG [hypershell.client] Received 4 task(s)
             INFO [hypershell.client] Running task (06b22512-c52f-4357-9d2b-2a4ab90adcb9)
            DEBUG [hypershell.client] Running task (06b22512-c52f-4357-9d2b-2a4ab90adcb9: bin/code.py data/source_01.h5 >output/source_01.out)
             INFO [hypershell.client] Running task (04188efc-7c18-4e6f-a358-5982a30c5f1e)
             INFO [hypershell.client] Running task (d2c28397-e668-4a31-b6d8-5d534226f165)
             INFO [hypershell.client] Running task (f36aa178-96fe-498d-ba19-e068bbcba027)
            DEBUG [hypershell.client] Running task (04188efc-7c18-4e6f-a358-5982a30c5f1e: bin/code.py data/source_02.h5 >output/source_02.out)
            DEBUG [hypershell.client] Running task (d2c28397-e668-4a31-b6d8-5d534226f165: bin/code.py data/source_03.h5 >output/source_03.out)
            DEBUG [hypershell.client] Running task (f36aa178-96fe-498d-ba19-e068bbcba027: bin/code.py data/source_04.h5 >output/source_04.out)
            DEBUG [hypershell.server] Scheduled task (0da02e5f-d3b2-483f-905c-3bdfc0df6b25)
            DEBUG [hypershell.server] Scheduled task (323c5fdd-1a7f-4db9-8897-29c03e8811d2)
            DEBUG [hypershell.server] Scheduled task (51e58f8e-0d3b-4e02-aec9-ff7f6fbe74c6)
            DEBUG [hypershell.server] Scheduled task (289079af-9513-48e3-885f-e762eea29a36)
            DEBUG [hypershell.client] Received 4 task(s)
            DEBUG [hypershell.server] Scheduled task (044a0423-553f-4b51-ab77-dec88a4732c6)
            DEBUG [hypershell.server] Scheduled task (94915027-ffde-4c4a-8768-2b09755d2900)
            DEBUG [hypershell.server] Scheduled task (5a4d520b-ad60-4388-afc5-d54b906ba1f7)
            DEBUG [hypershell.server] Scheduled task (49e68225-21c5-4383-b82c-068a41891177)
            DEBUG [hypershell.client] Received 4 task(s)
            DEBUG [hypershell.server] Scheduled task (5cc6d071-dd76-47ed-966e-4726c91a170d)
            DEBUG [hypershell.server] Scheduled task (47e1e543-f3b0-447c-93f9-5e5797fd4ccc)
            DEBUG [hypershell.server] Scheduled task (cc1f375a-4ea1-4572-8c60-855225fbfbdc)
            DEBUG [hypershell.server] Scheduled task (ca3db608-dbf4-4873-8f46-daff122835f6)
            DEBUG [hypershell.client] Completed task (06b22512-c52f-4357-9d2b-2a4ab90adcb9)
             INFO [hypershell.client] Running task (0da02e5f-d3b2-483f-905c-3bdfc0df6b25)
            DEBUG [hypershell.client] Running task (0da02e5f-d3b2-483f-905c-3bdfc0df6b25: bin/code.py data/source_05.h5 >output/source_05.out)
            DEBUG [hypershell.client] Completed task (d2c28397-e668-4a31-b6d8-5d534226f165)
             INFO [hypershell.client] Running task (323c5fdd-1a7f-4db9-8897-29c03e8811d2)
            DEBUG [hypershell.client] Running task (323c5fdd-1a7f-4db9-8897-29c03e8811d2: bin/code.py data/source_06.h5 >output/source_06.out)
            DEBUG [hypershell.client] Completed task (04188efc-7c18-4e6f-a358-5982a30c5f1e)
             INFO [hypershell.client] Running task (51e58f8e-0d3b-4e02-aec9-ff7f6fbe74c6)
            DEBUG [hypershell.client] Completed task (f36aa178-96fe-498d-ba19-e068bbcba027)
            DEBUG [hypershell.client] Running task (51e58f8e-0d3b-4e02-aec9-ff7f6fbe74c6: bin/code.py data/source_07.h5 >output/source_07.out)
             INFO [hypershell.client] Running task (289079af-9513-48e3-885f-e762eea29a36)
            DEBUG [hypershell.client] Running task (289079af-9513-48e3-885f-e762eea29a36: bin/code.py data/source_08.h5 >output/source_08.out)
            DEBUG [hypershell.client] Received 4 task(s)
            DEBUG [hypershell.server] Scheduled task (7169d11a-fe29-47e7-9534-b4dbf3fbd517)
            DEBUG [hypershell.server] Scheduled task (31b14bd8-a949-4fb2-a3b3-def60a9c1ae6)
            DEBUG [hypershell.server] Scheduled task (a85e03cf-e104-42c1-96ac-1d03c12abf40)
            DEBUG [hypershell.server] Scheduled task (daf4d145-19d2-4518-b976-71ac7c93256c)
            DEBUG [hypershell.server] Completed task (06b22512-c52f-4357-9d2b-2a4ab90adcb9)
            DEBUG [hypershell.server] Completed task (d2c28397-e668-4a31-b6d8-5d534226f165)
            DEBUG [hypershell.server] Completed task (04188efc-7c18-4e6f-a358-5982a30c5f1e)
            DEBUG [hypershell.server] Completed task (f36aa178-96fe-498d-ba19-e068bbcba027)
            DEBUG [hypershell.client] Completed task (0da02e5f-d3b2-483f-905c-3bdfc0df6b25)
             INFO [hypershell.client] Running task (044a0423-553f-4b51-ab77-dec88a4732c6)
            DEBUG [hypershell.client] Running task (044a0423-553f-4b51-ab77-dec88a4732c6: bin/code.py data/source_09.h5 >output/source_09.out)
            DEBUG [hypershell.client] Completed task (323c5fdd-1a7f-4db9-8897-29c03e8811d2)
             INFO [hypershell.client] Running task (94915027-ffde-4c4a-8768-2b09755d2900)
            DEBUG [hypershell.client] Running task (94915027-ffde-4c4a-8768-2b09755d2900: bin/code.py data/source_10.h5 >output/source_10.out)
            DEBUG [hypershell.client] Completed task (51e58f8e-0d3b-4e02-aec9-ff7f6fbe74c6)
             INFO [hypershell.client] Running task (5a4d520b-ad60-4388-afc5-d54b906ba1f7)
            DEBUG [hypershell.client] Running task (5a4d520b-ad60-4388-afc5-d54b906ba1f7: bin/code.py data/source_11.h5 >output/source_11.out)
            DEBUG [hypershell.client] Completed task (289079af-9513-48e3-885f-e762eea29a36)
             INFO [hypershell.client] Running task (49e68225-21c5-4383-b82c-068a41891177)
            DEBUG [hypershell.client] Running task (49e68225-21c5-4383-b82c-068a41891177: bin/code.py data/source_12.h5 >output/source_12.out)
            DEBUG [hypershell.client] Received 4 task(s)
            DEBUG [hypershell.server] Completed task (0da02e5f-d3b2-483f-905c-3bdfc0df6b25)
            DEBUG [hypershell.server] Completed task (323c5fdd-1a7f-4db9-8897-29c03e8811d2)
            DEBUG [hypershell.server] Completed task (51e58f8e-0d3b-4e02-aec9-ff7f6fbe74c6)
            DEBUG [hypershell.server] Completed task (289079af-9513-48e3-885f-e762eea29a36)
            DEBUG [hypershell.client] Completed task (044a0423-553f-4b51-ab77-dec88a4732c6)
             INFO [hypershell.client] Running task (5cc6d071-dd76-47ed-966e-4726c91a170d)
            DEBUG [hypershell.client] Running task (5cc6d071-dd76-47ed-966e-4726c91a170d: bin/code.py data/source_13.h5 >output/source_13.out)
            DEBUG [hypershell.client] Completed task (94915027-ffde-4c4a-8768-2b09755d2900)
             INFO [hypershell.client] Running task (47e1e543-f3b0-447c-93f9-5e5797fd4ccc)
            DEBUG [hypershell.client] Running task (47e1e543-f3b0-447c-93f9-5e5797fd4ccc: bin/code.py data/source_14.h5 >output/source_14.out)
            DEBUG [hypershell.client] Completed task (5a4d520b-ad60-4388-afc5-d54b906ba1f7)
             INFO [hypershell.client] Running task (cc1f375a-4ea1-4572-8c60-855225fbfbdc)
            DEBUG [hypershell.client] Running task (cc1f375a-4ea1-4572-8c60-855225fbfbdc: bin/code.py data/source_15.h5 >output/source_15.out)
            DEBUG [hypershell.client] Completed task (49e68225-21c5-4383-b82c-068a41891177)
             INFO [hypershell.client] Running task (ca3db608-dbf4-4873-8f46-daff122835f6)
            DEBUG [hypershell.client] Running task (ca3db608-dbf4-4873-8f46-daff122835f6: bin/code.py data/source_16.h5 >output/source_16.out)
            DEBUG [hypershell.server] Completed task (044a0423-553f-4b51-ab77-dec88a4732c6)
            DEBUG [hypershell.server] Completed task (94915027-ffde-4c4a-8768-2b09755d2900)
            DEBUG [hypershell.server] Completed task (5a4d520b-ad60-4388-afc5-d54b906ba1f7)
            DEBUG [hypershell.server] Completed task (49e68225-21c5-4383-b82c-068a41891177)
            DEBUG [hypershell.client] Completed task (5cc6d071-dd76-47ed-966e-4726c91a170d)
             INFO [hypershell.client] Running task (7169d11a-fe29-47e7-9534-b4dbf3fbd517)
            DEBUG [hypershell.client] Running task (7169d11a-fe29-47e7-9534-b4dbf3fbd517: bin/code.py data/source_17.h5 >output/source_17.out)
            DEBUG [hypershell.client] Completed task (cc1f375a-4ea1-4572-8c60-855225fbfbdc)
             INFO [hypershell.client] Running task (31b14bd8-a949-4fb2-a3b3-def60a9c1ae6)
            DEBUG [hypershell.client] Running task (31b14bd8-a949-4fb2-a3b3-def60a9c1ae6: bin/code.py data/source_18.h5 >output/source_18.out)
            DEBUG [hypershell.client] Completed task (47e1e543-f3b0-447c-93f9-5e5797fd4ccc)
             INFO [hypershell.client] Running task (a85e03cf-e104-42c1-96ac-1d03c12abf40)
            DEBUG [hypershell.client] Running task (a85e03cf-e104-42c1-96ac-1d03c12abf40: bin/code.py data/source_19.h5 >output/source_19.out)
            DEBUG [hypershell.client] Completed task (ca3db608-dbf4-4873-8f46-daff122835f6)
             INFO [hypershell.client] Running task (daf4d145-19d2-4518-b976-71ac7c93256c)
            DEBUG [hypershell.client] Running task (daf4d145-19d2-4518-b976-71ac7c93256c: bin/code.py data/source_20.h5 >output/source_20.out)
            DEBUG [hypershell.server] Completed task (5cc6d071-dd76-47ed-966e-4726c91a170d)
            DEBUG [hypershell.server] Completed task (cc1f375a-4ea1-4572-8c60-855225fbfbdc)
            DEBUG [hypershell.server] Completed task (47e1e543-f3b0-447c-93f9-5e5797fd4ccc)
            DEBUG [hypershell.server] Completed task (ca3db608-dbf4-4873-8f46-daff122835f6)
            DEBUG [hypershell.client] Completed task (7169d11a-fe29-47e7-9534-b4dbf3fbd517)
            DEBUG [hypershell.client] Completed task (a85e03cf-e104-42c1-96ac-1d03c12abf40)
            DEBUG [hypershell.client] Completed task (31b14bd8-a949-4fb2-a3b3-def60a9c1ae6)
            DEBUG [hypershell.client] Completed task (daf4d145-19d2-4518-b976-71ac7c93256c)
            DEBUG [hypershell.server] Completed task (7169d11a-fe29-47e7-9534-b4dbf3fbd517)
            DEBUG [hypershell.server] Completed task (a85e03cf-e104-42c1-96ac-1d03c12abf40)
            DEBUG [hypershell.server] Completed task (31b14bd8-a949-4fb2-a3b3-def60a9c1ae6)
            DEBUG [hypershell.server] Completed task (daf4d145-19d2-4518-b976-71ac7c93256c)
            DEBUG [hypershell.server] Done (scheduler)
            DEBUG [hypershell.server] Signaling clients (1 connected)
            DEBUG [hypershell.server] Disconnect requested (workstation.local: bf2e14e7-7afd-4e32-832f-dddddb405a31)
            DEBUG [hypershell.client] Disconnect received
            DEBUG [hypershell.client] Done (executor-1)
            DEBUG [hypershell.client] Done (executor-3)
            DEBUG [hypershell.client] Done (executor-4)
            DEBUG [hypershell.client] Done (executor-2)
            DEBUG [hypershell.client] Done (collector)
            DEBUG [hypershell.client] Done (heartbeat)
            DEBUG [hypershell.server] Done (heartbeat)
            DEBUG [hypershell.client] Done
            DEBUG [hypershell.server] Done (receiver)
            DEBUG [hypershell.server] Done

