~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Python USB API for Canon digital cameras
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:Homepage: http://packages.python.org/canon-remote/
:Author: Kiril Zyapkov <kiril.zyapkov@gmail.com>
:Copyright: 2012 Kiril Zyapkov
:Version: |release|
:Last updated: |today|

Table of Contents

.. toctree::
    :maxdepth: 2

    internals
    storage
    capture
    reference/canon

.. include:: ./../README.rst

Related projects
================

gphoto2_
    canon-remote wouldn't have existed if the USB protocol wasn't already
    reverse-engineered, and all the credit for that should go to gphoto2_.
    I can only imagine how many hours of sniffing USB packets and staring
    at hexdumps it took. Gphoto is great, but it is generic and huge. While
    it is actively developed, supports a vast number of cameras, has been
    extensively tested and comes with GUI tools, userspace filesystem
    driver, etc. etc., hacking it is a serious business, especially for
    someone not-so-much-C-profficient-or-keen.

capture_
    If Gphoto2 doesn't quite cut it for you, this will. Unless your camera
    is too old (like mine).

pycanon_
    A python wrapper for Canon's SDK. Couldn't use that, because Canon want
    you to agree not to reverse engineer it and/or release the information.
    Also, I try to avoid Windows as much as possible.

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

Quick Tour
==========

You need to have permissions to talk to your camera. Chances are you already
have `gphoto2` installed which has the necessary udev rules in place, your
user belongs to the right group, etc. If not, go make `gphoto2` work and
come back. Trying to use this as `root` would be pretty stupid.

To start playing with the driver, open up your `favorite python terminal`_::

    >>> from canon import camera
    >>> cam = camera.find() # look for a G3, pass idProduct for other models
    >>> cam.initialize() # this establishes the communication channel
    >>> cam
    <Canon PowerShot G3 v1.0.2.0>

The camera object has a bunch of properties, some of which are writable::

    >>> cam.firmware_version, cam.owner, cam.model
    ('1.0.2.0', 'adsf', 'Canon PowerShot G3')
    >>> cam.owner = 'me, not asdf'
    >>> cam.owner
    'me, not asdf'

You are probably interested in methods exposed by :attr:`storage` and
:attr:`capture` attributes of the :class:`Camera` instance ``cam``.

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
stored pcap files using `pcapy`_ which can be found in ``sandbox/``

.. _`Remote Capture`: http://software.canon-europe.com/software/0019449.asp
.. _virtualbox: https://www.virtualbox.org/
.. _gphoto-suite: https://svn.sourceforge.net/svnroot/gphoto/trunk/gphoto-suite
.. _Wireshark: http://wiki.wireshark.org/CaptureSetup/USB
.. _pcapy: http://oss.coresecurity.com/projects/pcapy.html
.. _favorite python terminal: http://bpython-interpreter.org/

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
