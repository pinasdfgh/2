#  This file is part of canon-remote.
#  Copyright (C) 2011-2012 Kiril Zyapkov <kiril.zyapkov@gmail.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import time
from array import array

import usb.core
import usb.util
from usb.core import USBError

from canon import CanonError, protocol, commands
from canon.capture import CanonCapture
from canon.storage import CanonStorage
from canon.util import extract_string, le32toi, itole32a, hexdump, le16toi

_log = logging.getLogger(__name__)

VENDORID = 0x04a9
PRODUCTID = 0x306e

def find():
    """Maybe support more cameras one day?
    """
    dev = usb.core.find(idVendor=VENDORID, idProduct=PRODUCTID)
    if not dev:
        _log.debug("Unable to find a Canon G3 camera attached to this host")
        return None
    _log.info("Found a Canon G3 on bus %s address %s", dev.bus, dev.address)
    return Camera(dev)

class Camera(object):
    """Interface with a Camera.

    A camera should look like this:
    >>> cam.owner                        # supports a number of properties
        'The owner string'
    >>> cam.owner = 'Mine!'              # some of which writable
    >>> cam.owner
        'Mine!'
    >>> cam.fs_walk()                    # os.walk() but over camera storage
    >>> cam.fs_get(filename, target)     # store contents of filename to
                                         # the file-like object ``target``
    >>> cam.begin_capture()              # capture mode is special
    >>> cam.end_capture()
    >>> cam.in_capture
        True
    >>> cam.shooting_mode
    >>> cam.image_format
    >>> cam.iso
    >>> cam.speed
    >>> cam.capture()
    """

    def __init__(self, device):
        self._device = device
        self._usb = protocol.CanonUSB(device)
        self._storage = CanonStorage(self._usb)
        self._capture = CanonCapture(self._usb)
        self._abilities = None

    @property
    def storage(self):
        """Access the camera filesystem.
        """
        return self._storage

    @property
    def capture(self):
        """Do remote captures.
        """
        return self._capture

    def initialize(self, force=False):
        if self._usb.ready and not force:
            _log.info("initialize called, but camera seems up, force me")
            return
        _log.info("camera will be initialized")
        self._usb.initialize()
        c = commands.GenericLockKeysCmd()
        c.execute(self._usb)

    @property
    def ready(self):
        try:
            return bool(self.identify())
        except (USBError, CanonError):
            return False

    def identify(self):
        """ identify() -> (model, owner, version)
        """
        c = commands.IdentifyCameraCmd()
        return c.execute(self._usb)

    @property
    def owner(self):
        """The owner of this camera, writable.
        """
        return self.identify()[1]

    @owner.setter
    def owner(self, owner):
        commands.SetOwnerCmd(owner).execute(self._usb)

    @property
    def model(self):
        """Camera model string as stored on it.
        """
        return self.identify()[0]

    @property
    def firmware_version(self):
        return self.identify()[2]

    @property
    def camera_time(self):
        """Get the current date and time stored and ticking on the camera.
        """
        return commands.GetTimeCmd().execute(self._usb)

    @camera_time.setter
    def camera_time(self, new):
        """Set the current date and time.

        Currently only accepts an UNIX timestamp, should be translated
        to the local timezone.
        """
        # TODO: convert to local tz, accept datetime
        if new is None:
            new = time.time()
        new = int(new)
        commands.SetTimeCmd(new).execute(self._usb)

    @property
    def on_ac(self):
        """True if the camera is not running on battery power.
        """
#        data = commands.GetPowerStatusCmd().execute(self._usb)
#        return bool((data[0x17] & 0x20) == 0x00)
        return commands.CheckACPowerCmd().execute(self._usb)

    @property
    def abilities(self):
        """ http://www.graphics.cornell.edu/~westin/canon/ch03s25.html
        """
        if not self._abilities:
            return self.get_abilities()
        return self._abilities

    def get_abilities(self):
        self._abilities = commands.GetPicAbilitiesCmd().execute(self._usb)
        return self._abilities

    def cleanup(self):
        _log.info("Camera {} being cleaned up".format(self))
        try:
            if self.capture.active:
                self.capture.stop()
        except:
            pass
        self._usb = None
        self._storage = None
        self._capture = None
        if self._device:
            usb.util.dispose_resources(self._device)
            self._device = None

    def __repr__(self):
        ret = object.__repr__(self)
        if self.ready:
            try:
                return "<{} {} {}>".format(self.model, self.firmware_version,
                                           self.owner)
            except:
                return ret
        else:
            return ret


    def __del__(self):
        self.cleanup()
