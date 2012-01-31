~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Python USB API for Canon digital cameras
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:Homepage: http://packages.python.org/canon-remote/
:Author: Kiril Zyapkov <kiril.zyapkov@gmail.com>
:Copyright: 2012 Kiril Zyapkov
:Version: |release|
:Last updated: |today|

..
    .. toctree::
        reference/canon

Overview
========

The contents of `README.rst`  follow, may as well skip `forward`_.

.. include:: ./../README.rst

.. _forward:

Installation
============

canon-remote_ depends only on pyusb_ version 1.0 or later. It was only tested
with `libusb-1.0` and `Python 2.7` on a 64bit linux box. It will not work on
any older Python versions and might work on Python 3.x with the ``2to3`` tool.

Installation should work fine via `easy_install` or `pip`::

    $ pip install canon-remote

or the plain old::

    $ python setup.py install

once you get `the source`_.

Usage
=====

You need to have permissions to talk to your camera. Chances are you already
have `gphoto2` installed which has the necessary udev rules in place, your
user belongs to the right group, etc. If not, go make `gphoto2` work and
come back. Trying to use this as `root` would be pretty stupid.

To start playing with the driver, open up your `favorite python terminal`_::

    >>> from canon import camera
    >>> cam = camera.find() # look for a G3, pass idProduct for other models
    >>> cam
    <Canon PowerShot G3 v1.0.2.0>

The camera object has a bunch of properties, some of which are writable::

    >>> cam.firmware_version, cam.owner, cam.model
    ('1.0.2.0', 'adsf', 'Canon PowerShot G3')
    >>> cam.owner = 'me, not asdf'
    >>> cam.owner
    'me, not asdf'

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

And so much for reliably implemented features.

The ``cam`` object above has two more interesting attributes:

    :attr:`storage`
        which exposes functions for accessing the camera filesystem, and

    :attr:`capture`
        which allows taking pictures.

If you're into hacking this, I recommend adding the path to your working
copy of `canon-remote` to a .pth file, or using virutalenv. You could set the
logging level to DEBUG to see all USB traffic and other helpful stuff.

Related Projects
================

http://www.gphoto.org/

http://www.reynoldsnet.org/s10sh/

http://www.kyuzz.org/antirez/s10sh.html

http://www.darkskiez.co.uk/index.php?page=Canon_Camera_Hacking

http://alexbernstein.com/wiki/canon-digital-rebel-300d-hacking/

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _favorite python terminal: http://bpython-interpreter.org/
