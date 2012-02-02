Internals
=========

If you did the Quick Tour and it worked for you, you should have a ``cam``
object in your console ready to be explored.

Setting the :attr:`owner` attribute caused a command to be sent to the
camera. To get an idea what's going on, look at the log::

    >>> import logging
    >>> l = logging.getLogger('canon')
    >>> l.addHandler(logging.StreamHandler())
    >>> l.setLevel(logging.INFO)
    >>> cam.owner = 'Kiril'
    --> SetOwnerCmd (0x5, 0x12, 0x201), #5
    control_write (rt: 0x40, req: 0x4, wValue: 0x10) 0x56 bytes
    bulk_read got 64 (0x40) b in 0.002964 sec
    bulk_read got 20 (0x14) b in 0.001549 sec
    <-- SetOwnerCmd #5 status: 0x0
    --> IdentifyCameraCmd (0x1, 0x12, 0x201), #10
    control_write (rt: 0x40, req: 0x4, wValue: 0x10) 0x50 bytes
    bulk_read got 128 (0x80) b in 0.003996 sec
    <-- IdentifyCameraCmd #10 status: 0x0
    bulk_read got 28 (0x1c) b in 0.001196 sec

So setting :attr:`owner` caused a ``SetOwnerCmd`` to be executed, followed
by an ``IdentifyCameraCmd``. To admire a real time dump of all USB traffic,
set the log level to ``DEBUG``::

    >>> l.setLevel(logging.DEBUG)
    >>> cam.identify() # a slightly fancier logging format here ...
    1327981738.91656 INFO   commands.py:239   --> IdentifyCameraCmd (0x1, 0x12, 0x201), #12
    1327981738.91735 INFO   protocol.py:256   control_write (rt: 0x40, req: 0x4, wValue: 0x10) 0x50 bytes
    1327981738.91797 DEBUG  protocol.py:257
    0000  10 00 00 00 01 02 00 00  00 00 00 00 00 00 00 00   ;...;;.. ........
    0010  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
    0020  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
    0030  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
    0040  02 00 00 00 01 00 00 12  10 00 00 00 0c 00 12 00   ;...;..; ;...;.;.
    1327981738.92518 INFO   protocol.py:277   bulk_read got 128 (0x80) b in 0.003977 sec
    1327981738.92605 DEBUG  protocol.py:278
    0000  5c 00 00 00 01 03 00 00  00 00 00 00 00 00 00 00   \...;;.. ........
    0010  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
    0020  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
    0030  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
    0040  02 00 00 00 01 00 00 22  5c 00 00 00 0c 00 12 00   ;...;.." \...;.;.
    0050  00 00 00 00 01 06 15 83  00 02 00 01 43 61 6e 6f   ....;;;; .;.;Cano
    0060  6e 20 50 6f 77 65 72 53  68 6f 74 20 47 33 00 00   n PowerS hot G3..
    0070  00 00 00 00 00 00 00 00  00 00 00 00 4b 69 72 69   ........ ....Kiri
    1327981738.92663 INFO   commands.py:339   <-- IdentifyCameraCmd #12 status: 0x0
    1327981738.92818 INFO   protocol.py:277   bulk_read got 28 (0x1c) b in 0.001210 sec
    1327981738.92868 DEBUG  protocol.py:278
    0000  6c 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   l....... ........
    0010  00 00 00 00 00 00 00 00  00 00 00 00               ........ ....
    ('Canon PowerShot G3', 'Kiril', '1.0.2.0')

