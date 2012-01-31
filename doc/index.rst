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

..
    Overview
    ========

    The contents of `README.rst`  follow, may as well skip `forward`_.

.. include:: ./../README.rst

.. _forward:

Related projects
================

gphoto2_
    canon-remote wouldn't have existed if the USB protocol wasn't already
    reverse-engineered, and all the credit for that should go to gphoto2_.
    I can only imagine how many hours of sniffing USB packets and staring
    at hexdumps it took. Gphoto is great, but it is generic and huge. While
    it is actively developed, supports a vast number of cameras, has been
    extensively tested and comes with GUI tools, userspace filesystem d
    river, etc. etc., hacking it is a serious business, especially for
    someone not-so-much-C-profficient-or-keen.

capture_
    If Gphoto2 doesn't quite cut it for you, this will. Unless your camera
    is too old (like mine).

pycanon_
    A python wrapper for Canon's SDK. Couldn't use that, because Canon want
    you to agree not to reverse engineer it and/or release the information.
    Also, I don't own a Windows machine.

s10sh_
    This is another really old little tool which talks to Canons.

.. _s10sh: http://www.reynoldsnet.org/s10sh/
.. _pycanon: http://pypi.python.org/pypi/pycanon/
.. _capture: http://capture.sourceforge.net/

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

Not much of those has been implemented, tested or documented yet.

Development
===========

This is what I did to setup the environemnt `canon-remote` was developed in.
I am sure there are other approaches, but this may be helpful for anyone
willing to give it a shot.

Checkout `gphoto2`. It's a bundle of software packages, the easiest way to
get everything you need is to use the `gphoto-suite`_ "umbrella package"::

    $ svn co https://svn.sourceforge.net/svnroot/gphoto/trunk/gphoto-suite gphoto-suite

Or, you could only get the source of `libgphoto2` and look at
``libgphoto2/camlibs/canon/``.

A way to sniff and analyze USB traffic is a must. I am using the
original `Remote Capture`_ from Canon on Windows XP within a
virtualbox_ machine. See `this
<http://www.virtualbox.org/manual/ch03.html#idp11216576>`_ on how to
enable USB support in a virtualbox guest. Wireshark_ runs on the host
sniffing USB traffic. I wrote a small script to parse commands from
stored pcap files using `pcapy`_.

.. _`Remote Capture`: http://software.canon-europe.com/software/0019449.asp
.. _virtualbox: https://www.virtualbox.org/
.. _gphoto-suite: https://svn.sourceforge.net/svnroot/gphoto/trunk/gphoto-suite
.. _Wireshark: http://wiki.wireshark.org/CaptureSetup/USB
.. _pcapy: http://oss.coresecurity.com/projects/pcapy.html

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _favorite python terminal: http://bpython-interpreter.org/
