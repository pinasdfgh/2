About this project
------------------

canon-remote_ is a USB library for Canon digital cameras in Python
with  pyusb_. It originally started as a Python port of gphoto2_'s
`Canon library`_ for a PowerShot G3. Only the subset necessary for
this model was ported, but it should be usable with other models from
that era (not without hacking) and will almost surely not work on much
newer cameras, not without serious hacking. The project was created
because gphoto2 lacks support for certain remote capture features,
namely locking the autofocus and setting the autofocus mode to macro.

The latest project documentation can be found at the `project homepage`_.
Or you can build it from source.

`The source`_ is hosted at `bitbucket`_.

You can contact me at kiril.zyapkov@gmail.com.

License
-------

`canon-remote`_ is licensed under GPLv3_.

Disclaimer
----------

Canon is a registered trademark of `Canon Inc.`_ This project is an
unofficial implementation of their closed USB camera protocol. I am not
affiliated with Canon Inc. No information or code from them was used
for this work. The protocol was reverse-engineered by the guys behind
gphoto2_, thanks guys!

.. warning::
    Use this at **your own risk**. I haven't damaged my camera with it yet,
    but it's not impossible.

.. _project homepage:
.. _canon-remote: http://packages.python.org/canon-remote/
.. _pyusb: http://sourceforge.net/apps/trac/pyusb/
.. _gphoto2: http://www.gphoto.org/
.. _Canon library: http://gphoto.svn.sourceforge.net/viewvc/gphoto/trunk/libgphoto2/camlibs/canon/
.. _Canon Inc.: http://www.canon.com
.. _bitbucket: http://bitbucket.org
.. _The source: http://bitbucket.org/xxcn/canon-remote/
.. _GPLv3: http://gplv3.fsf.org/
