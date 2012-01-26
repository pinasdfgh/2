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

    def __init__(self, device):
        self._device = device
        self._usb = protocol.CanonUSB(device)
        self._storage = CanonStorage(self._usb)
        self._capture = CanonCapture(self._usb)
        self._in_rc = False

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
        self._usb.do_command(commands.GENERIC_LOCK_KEYS)

    @property
    def ready(self):
        try:
            return bool(self.identify())
        except (USBError, CanonError):
            return False

    def identify(self):
        """ identify() -> (model, owner, version)
        """
        data = self._usb.do_command(commands.IDENTIFY_CAMERA, full=False)
        model = extract_string(data, 0x1c)
        owner = extract_string(data, 0x3c)
        version = '.'.join([str(x) for x in data[0x1b:0x17:-1]])
        return model, owner, version

    @property
    def owner(self):
        """The owner of this camera, writable.
        """
        return self.identify()[1]

    @owner.setter
    def owner(self, owner):
        self._usb.do_command(commands.CAMERA_CHOWN, owner + '\x00')

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
        resp = self._usb.do_command(commands.GET_TIME, full=False)
        return le32toi(resp[0x14:0x14 + 4])

    @camera_time.setter
    def camera_time(self, new):
        """Set the current date and time.

        Currently only accepts an UNIX timestamp, should be translated
        to the local timezone.
        """
        if new is None:
            # TODO: convert to local tz, accept datetime
            new = time.time()
        new = int(new)
        self._usb.do_command(commands.SET_TIME, itole32a(new) + array('B', [0] * 8))
        return self.camera_time

    @property
    def on_ac(self):
        """True if the camera is not running on battery power.
        """
        data = self._usb.do_command(commands.POWER_STATUS, full=False)
        return bool((data[0x17] & 0x20) == 0x00)

    @property
    def abilities(self):
        """ http://www.graphics.cornell.edu/~westin/canon/ch03s25.html
        """
        data = self._usb.do_command(commands.GET_PIC_ABILITIES, full=True)
        struct_size = le16toi(data, 0x54)
        model_id = le32toi(data[0x56:0x5a])
        camera_name = extract_string(data, 0x5a)
        num_entries = le32toi(data, 0x7a)
        _log.info("abilities of {} (0x{:x}): 0x{:x} long, n={}"
                 .format(camera_name, model_id, struct_size, num_entries))
        offset = 0x7e
        abilities = []
        for i in xrange(num_entries):
            name = extract_string(data, offset)
            height = le32toi(data, offset + 20)
            width = le32toi(data, offset + 24)
            z_types = le32toi(data, offset + 28)
            _log.info(" {:-3} - {:20} {}x{} {:x}".format(i, name, width, height, z_types))
            offset += 32
            abilities.append((name, height, width, z_types))

        return abilities

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
