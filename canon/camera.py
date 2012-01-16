#
# This file is part of canon-remote
# Copyright (C) 2011 Kiril Zyapkov
#
# canon-remote is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# canon-remote is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with canon-remote.  If not, see <http://www.gnu.org/licenses/>.
#

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
    dev = usb.core.find(idVendor=VENDORID, idProduct=PRODUCTID)
    if not dev:
        _log.debug("Unable to find a Canon G3 camera attached to this host")
        return None
    _log.info("Found a Canon G3 on bus %s address %s", dev.bus, dev.address)
    return Camera(dev)

class Camera(object):

    def __init__(self, device):
        self.device = device
        self._usb = protocol.CanonUSB(device)
        self._storage = CanonStorage(self._usb)
        self._capture = CanonCapture(self._usb)
        self._in_rc = False

    @property
    def storage(self):
        return self._storage

    @property
    def capture(self):
        return self._capture

    def initialize(self, force=False):
        if self._usb.ready and not force:
            _log.info("initialize called, but camera seems up, force me")
            return
        _log.info("camera will be initialized")
        return self._usb.initialize()

    def is_ready(self):
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
    def camera_time(self):
        """Get the current date and time stored and ticking on the camera.
        """
        resp = self._usb.do_command(commands.GET_TIME, full=False)
        return le32toi(resp[0x14:0x14 + 4])

    @camera_time.setter
    def camera_time(self, new):
        """Set the current date and time.

        Currently only accepts UNIX timestamp, should be translated to the
        local timezone.
        """
        if new is None:
            # TODO: convert to local tz, accept datetime
            new = time.time()
        new = int(new)
        self._usb.do_command(commands.SET_TIME, itole32a(new) + array('B', [0] * 8))
        return self.camera_time

    @property
    def owner(self):
        return self.identify()[1]

    @owner.setter
    def owner(self, owner):
        self._usb.do_command(commands.CAMERA_CHOWN, owner + '\x00')

    @property
    def on_ac(self):
        """True if the camera is not running on battery power.
        """
        data = self._usb.do_command(commands.POWER_STATUS, full=False)
        return bool((data[0x17] & 0x20) == 0x00)

    def get_pic_abilities(self):
        data = self._usb.do_command(commands.GET_PIC_ABILITIES, full=True)
        status = le32toi(data, 0x50)
        struct_size = le16toi(data, 0x54)
        model_id = le32toi(data, 0x56)
        cam_id = extract_string(data[0x5a:0x5a + 0x20])
        _log.info("pic abilities: status {}, size {}, model {}, cam {}"
                  .format(status, struct_size, model_id, cam_id))

    def cleanup(self):
        _log.info("Camera {} being cleaned up".format(self))
        try:
            if self.capture.active:
                self.rc.stop()
        except:
            pass
        self._usb = None
        self._storage = None
        self._capture = None
        if self.device:
            usb.util.dispose_resources(self.device)
            self.device = None

    def __del__(self):
        self.cleanup()
