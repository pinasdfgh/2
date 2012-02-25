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
    Camera objects are the intended API endpoint. Cameras have two
    properties which provide most of the interesting functionality:

     * :attr:`storage` for filesystem operations, and
     * :attr:`capture` for taking pictures.

    Camera objects also expose generic properties of the camera as attributes:
    :attr:`firmware_version`, :attr:`owner`, :attr:`model`,
    :attr:`camera_time`.
    """

    def __init__(self, device):
        """Connect to a :class:`usb.core.Device`.
        """
        self._device = device
        self._usb = protocol.CanonUSB(device)
        self._storage = CanonStorage(self._usb)
        self._capture = CanonCapture(self._usb)
        self._abilities =None
        self._model = None
        self._owner = None
        self._firmware_version = None

    @property
    def ready(self):
        """Check if the camera has been initialized.

        gphoto2 source claims that this command doesn't change the state
        of the camera and can safely be issued without any side effects.

        """
        if not self._device:
            return False
        try:
            commands.IdentifyCameraCmd().execute(self._usb)
            return True
        except (USBError, CanonError):
            return False

    def initialize(self):
        """Bring the camera into a state where it accepts commands.

        This method needs to be called on newly-created instances in order
        to handshake with the camera and make it listen to us.
        There:
        http://www.graphics.cornell.edu/~westin/canon/ch03.html#sec.USBCameraInit

        """
        try:
            cfg = self._device.get_active_configuration()
            _log.debug("Configuration %s already set.", cfg.bConfigurationValue)
        except USBError, e:
            _log.debug("Will attempt to set configuration now, {}".format(e))
            self._device.set_configuration()
            self._device.set_interface_altsetting()

        # Clear endpoint HALTs, not sure if needed, but doesn't hurt
        for ep in (self._usb.ep_in, self._usb.ep_int, self._usb.ep_out):
            try:
                usb.control.clear_feature(self._device, usb.control.ENDPOINT_HALT, ep)
            except USBError, e:
                _log.info("Clearing HALT on {} failed: {}".format(ep, e))

        # while polling, with a gracious timeout, do the dance
        with self._usb.poller_ctx() as p, self._usb.timeout_ctx(2000):
            camstat = self._usb.control_read(0x55, 1).tostring()
            if camstat not in ('A', 'C'):
                raise CanonError('Some kind of init error, camstat: %s', camstat)

            msg = self._usb.control_read(0x01, 0x58)
            if camstat == 'A':
                _log.debug("Camera was already active")
                self._usb.control_read(0x04, 0x50)
                return camstat

            _log.debug("Camera woken up, initializing")

            msg[0:0x40] = array('B', [0]*0x40)
            msg[0] = 0x10
            msg[0x40:] = msg[-0x10:]
            self._usb.control_write(0x11, msg)
            self._usb.bulk_read(0x44)

            started = time.time()
            while len(p.received) < 0x10:
                time.sleep(0.2)
                if time.time() - started > 3.0: # maybe too long
                    # when this happens we're usually ok to proceed ...
                    #raise CanonError("Waited for interrupt in data for too long!")
                    _log.error("Waited for interrupt data for too long!")
                    break

        for _ in range(3):
            try:
                self.identify()
                break
            except (USBError, CanonError), e:
                _log.debug("identify after init fails: {}".format(e))
        if not self.ready:
            raise CanonError("identify_camera failed too many times")

        commands.GenericLockKeysCmd().execute(self._usb)
        self._storage.initialize()
        self._capture.initialize()

    @property
    def storage(self):
        """Access the camera filesystem API.

        See :class:`CanonStorage`.

        """
        return self._storage

    @property
    def capture(self):
        """Access the remote control&capture API.

        See :class:`CanonCapture`.

        """
        return self._capture

    def identify(self):
        """ Return an (model, owner, version) tuple.
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
        """Camera model string.
        """
        if not self._model:
            return self.identify()[0]
        return self._model

    @property
    def firmware_version(self):
        """Firmware version as reported by :class:`IdentifyCameraCmd`.
        """
        if not self._firmware_version:
            return self.identify()[2]
        return self._firmware_version

    @property
    def camera_time(self):
        """Camera time as localized unix timestamp, writable.
        """
        return commands.GetTimeCmd().execute(self._usb)

    @camera_time.setter
    def camera_time(self, new):
        # TODO: convert to local tz, accept datetime
        if new is None:
            new = time.time()
        new = int(new)
        commands.SetTimeCmd(new).execute(self._usb)

    @property
    def on_ac(self):
        """True if the camera is not running on battery power.
        """
        return commands.CheckACPowerCmd().execute(self._usb)

    @property
    def abilities(self):
        """Camera "abilities" -- supported image sizes and compressions.
        """
        if not self._abilities:
            return self.get_abilities()
        return self._abilities

    def get_abilities(self):
        """Fetch "abilities" from camera.

        This data isn't used in the protocol, it seems noone figured out a way
        to do so. Data format is explained `here
        <http://www.graphics.cornell.edu/~westin/canon/ch03s25.html>`_.

        """
        self._abilities = commands.GetPicAbilitiesCmd().execute(self._usb)
        return self._abilities

    def cleanup(self):
        """Dispose resources, disable remote capture mode if necessary.
        """
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
