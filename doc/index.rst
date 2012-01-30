****************************************
Python USB API for Canon digital cameras
****************************************

:Homepage: canon-remote_
:Author: Kiril Zyapkov <kiril.zyapkov@gmail.com>
:Copyright: 2012 Kiril Zyapkov
:Version: |release|
:Last updated: |today|

.. include:: ../../README.rst

Installation
============

`canon-remote` depends on `pyusb` version 1.0 or later. It was only tested
with `libusb-1.0` and Python 2.7 on a 64bit linux box. It will not work on
any older Python versions and might work on Python 3.x with the ``2to3`` tool.

Installation should work fine via `easy_install` or `pip`, or the plain old::

    python setup.py install


Usage
=====

To start playing with the driver, open up your `favorite python terminal`_::

  >>> from canon import camera
  >>> cam = camera.find() # look for a G3, pass idProduct for other models
  >>> cam
  <Canon PowerShot G3 firmware 1.0.2.0 owned by kiril.zyapkov@gmail.com>


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

API
===

.. automodule:: canon.camera
   :members: find, Camera

USB Protocol
------------

.. automodule:: canon.protocol
   :members:
.. automodule:: canon.commands
   :members:

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _favorite python terminal: http://bpython-interpreter.org/
