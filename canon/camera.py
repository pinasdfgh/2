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

# Canon
VENDORID = 0x04a9
# PowerShot G3
PRODUCTID = 0x306e

def find(idVendor=VENDORID, idProduct=PRODUCTID):
    """Find a canon camera on some usb bus, possibly.

    Pass in idProduct for your particular model, default values are for a
    PowerShot G3.

    """
    dev = usb.core.find(idVendor=idVendor, idProduct=idProduct)
    if not dev:
        _log.debug("Unable to find a Canon G3 camera attached to this host")
        return None
    _log.info("Found a Canon G3 on bus %s address %s", dev.bus, dev.address)
    return Camera(dev)

class Camera(object):
    """
    Camera objects are the intended API endpoint. Cameras have two public
    properties which provide most of the interesting functionality:
     * ``storage`` for filesystem operations, and
     * ``capture`` for taking pictures.

    """

    def __init__(self, device):
        self._device = device
        self._usb = protocol.CanonUSB(device)
        self._storage = CanonStorage(self._usb)
        self._capture = CanonCapture(self._usb)
        self._abilities =None
        self._model = None
        self._owner = None
        self._firmware_version = None

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
        else:
            _log.info("camera will be initialized")
            try:
                self._usb.initialize()
            except USBError, e:
                _log.info("the init dance failed: {}".format(e))
                if not self.ready:
                    raise

        commands.GenericLockKeysCmd().execute(self._usb)
        self._storage.initialize(force)
        self._capture.initialize(force)

    @property
    def ready(self):
        if not self._device:
            return False
        try:
            self.identify()
            return True
        except (USBError, CanonError):
            return False

    def identify(self):
        """ identify() -> (model, owner, version)
        """
        info = commands.IdentifyCameraCmd().execute(self._usb)
        (self._model, self._owner, self._firmware_version) = info
        return info

    @property
    def owner(self):
        """The owner of this camera, writable.
        """
        if not self._owner:
            return self.identify()[1]
        return self._owner

    @owner.setter
    def owner(self, owner):
        commands.SetOwnerCmd(owner).execute(self._usb)
        self.identify()

    @property
    def model(self):
        """Camera model string as stored on it.
        """
        if not self._model:
            return self.identify()[0]
        return self._model

    @property
    def firmware_version(self):
        if not self._firmware_version:
            return self.identify()[2]
        return self._firmware_version

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
        #data = commands.GetPowerStatusCmd().execute(self._usb)
        #return bool((data[0x17] & 0x20) == 0x00)
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
        if not self._device:
            return
        _log.info("Camera {} being cleaned up".format(self))
        usb.util.dispose_resources(self._device)
        self._device = None
        try:
            if self.capture.active:
                self.capture.stop()
        except:
            pass
        self._usb = None
        self._storage = None
        self._capture = None

    def __repr__(self):
        ret = object.__repr__(self)
        if self.ready:
            try:
                return "<{} v{}>".format(self.model, self.firmware_version)
            except:
                return ret
        else:
            return ret

    def __del__(self):
        self.cleanup()
