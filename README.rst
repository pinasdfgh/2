canon-remote_
=============

:Homepage: http://1024.cjb.net/canon-remote/
:Author: Kiril Zyapkov <kiril.zyapkov@gmail.com>
:Copyright: 2012 Kiril Zyapkov
:Last updated: |today|

`canon-remote`_ is a USB interface for Canon digital cameras in Python. It
originally started as a python port of `gphoto2`_'s `Canon library`_ for a
PowerShot G3. Only the subset necessary for this model was ported, but it
should be usable with other models from that era. The project
was created because gphoto2 lacks support for certain remote capture
features, namely locking the autofocus and setting the autofocus mode
to macro.

Canon is a registered trademark of `Canon Inc.`_ This project is an
unofficial implementation of their closed USB camera protocol. I am not
affiliated with Canon Inc. and no information from them was used
for this work. It is solely the result of reverse-engineering effort.

The latest project documentation can be found at the `project homepage`_

Source is hosted on TODO: hosting

.. _canon-remote: http://1024.cjb.net/canon-remote/
.. _gphoto2: http://www.gphoto.org/
.. _Canon library: http://gphoto.svn.sourceforge.net/viewvc/gphoto/trunk/libgphoto2/camlibs/canon/
.. _Canon Inc.: http://www.canon.com

Installation
------------

`canon-remote` depends on `pyusb` version 1.0 or later. It was only tested
with `libusb-1.0` and Python 2.7 on a 64bit linux box. It will not work on
any older Python versions and might work on Python 3.x with the ``2to3`` tool.

Installation should work fine via `easy_install` or `pip`, or the plain old::
    python setup.py install


Advanced Usage and Development on Linux
---------------------------------------

If you're into hacking this, I recommend adding the path to your working
copy of `canon-remote` to a .pth file, or using virutalenv. You could set the
logging level to DEBUG to see all USB traffic and other helpful stuff.

Related Projects
----------------

http://www.gphoto.org/

http://www.reynoldsnet.org/s10sh/

http://www.kyuzz.org/antirez/s10sh.html

http://www.darkskiez.co.uk/index.php?page=Canon_Camera_Hacking

http://alexbernstein.com/wiki/canon-digital-rebel-300d-hacking/
