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

"""Communicate with a Canon camera, old style.

This protocol implementation is heavily based on
http://www.graphics.cornell.edu/~westin/canon/index.html
and gphoto2's source. Sporadic comments here are mostly copied from
gphoto's source and docs.

-- need to put that somewhere --
wValue differs between operations.
wIndex is always 0x00
wLength is simply the length of data.

"""

import time
import threading
import logging
from array import array
from contextlib import contextmanager

import usb.util
from usb.core import USBError

from canon import commands, CanonError
from canon.util import le32toi, hexdump, itole32a, Bitfield

_log = logging.getLogger(__name__)

MAX_CHUNK_SIZE = 0x1400

class InterruptPoller(threading.Thread):
    """Poll the interrupt pipe on a CanonUSB.

    This should not be instantiated directly, but via CanonUSB.poller
    """
    def __init__(self, usb, size=None, chunk=0x10, timeout=None):
        threading.Thread.__init__(self)
        self.usb = usb
        self.should_stop = False
        self.size = size
        self.chunk = chunk
        self.received = array('B')
        self.timeout = int(timeout) if timeout is not None else 150
        self.setDaemon(True)

    def run(self):
        errors = 0
        while errors < 10:
            if self.should_stop: return
            try:
                chunk = self.usb.interrupt_read(self.chunk, self.timeout)
                if chunk:
                    self.received.extend(chunk)
                if (self.size is not None
                        and len(self.received) >= self.size):
                    _log.info("poller got 0x{:x} bytes, needed 0x{:x}"
                              ", exiting".format(len(self.received),
                                                 self.size))
                    return
                if self.should_stop:
                    _log.info("poller stop requested, exiting")
                    return
                time.sleep(0.1)
            except (USBError, ) as e:
                if e.errno == 110: # timeout, ignore
                    continue
                if e.errno == 16: # resource busy, bail
                    _log.warn("interrupt pipe busy: {}".format(e))
                    return
                _log.warn("poll: {}".format(e))
                errors += 1
        _log.info("poller got too many errors, exiting")

    def stop(self):
        self.should_stop = True
        self.join()

class CanonUSB(object):
    """USB Link to the camera.
    """
    def __init__(self, device):
        self.max_chunk_size = MAX_CHUNK_SIZE
        self.device = device
        self.device.default_timeout = 500
        self.iface = iface = device[0][0,0]

        # Other models may have different endpoint addresses
        self.ep_in = usb.util.find_descriptor(iface, bEndpointAddress=0x81)
        self.ep_out = usb.util.find_descriptor(iface, bEndpointAddress=0x02)
        self.ep_int = usb.util.find_descriptor(iface, bEndpointAddress=0x83)
        self._cmd_serial = 0
        self._poller = None

    @contextmanager
    def timeout_ctx(self, new):
        old = self.device.default_timeout
        self.device.default_timeout = new
        _log.info("timeout_ctx: {} ms -> {} ms".format(old, new))
        now = time.time()
        try:
            yield
        finally:
            _log.info("timeout_ctx: {} ms <- {} ms; back in {:.3f} ms"
                      .format(old, new, (time.time() - now) * 1000))
            self.device.default_timeout = old

    def start_poller(self, size=None, timeout=None):
        if self._poller and self._poller.isAlive():
            raise CanonError("Poller already started.")
        self._poller = InterruptPoller(self, size, timeout=timeout)
        self._poller.start()

    def stop_poller(self):
        if not self._poller:
            raise CanonError("There's no poller to stop.")
        if self._poller.isAlive():
            self._poller.stop()
        self._poller = None

    @property
    def is_polling(self):
        return bool(self._poller and self._poller.isAlive())

    @property
    def poller(self):
        return self._poller

    @contextmanager
    def poller_ctx(self, size=None, timeout=None):
        if self.is_polling:
            raise CanonError("Cannot enter poller context while already polling")
        self.start_poller(size, timeout)
        yield self._poller
        if self.is_polling:
            self.stop_poller()

    def is_ready(self):
        """Check if the camera has been initialized by issuing IDENTIFY_CAMERA.

        gphoto2 source claims that this command doesn't change the state
        of the camera and can safely be issued without any side effects.

        """
        try:
            commands.IdentifyCameraCmd().execute(self)
            return True
        except (USBError, CanonError):
            return False

    ready = property(is_ready)

    def initialize(self):
        """Bring the camera into a state where it accepts commands.

        There:
        http://www.graphics.cornell.edu/~westin/canon/ch03.html#sec.USBCameraInit

        """
        try:
            cfg = self.device.get_active_configuration()
            _log.debug("Configuration %s already set.", cfg.bConfigurationValue)
        except USBError, e:
            _log.debug("Will attempt to set configuration now, {}".format(e))
            self.device.set_configuration()
            self.device.set_interface_altsetting()

        for ep in (self.ep_in, self.ep_int, self.ep_out):
            try:
                usb.control.clear_feature(self.device, usb.control.ENDPOINT_HALT, ep)
            except USBError, e:
                _log.info("Clearing HALT on {} failed: {}".format(ep, e))

        with self.poller_ctx() as p, self.timeout_ctx(2000):
            camstat = self.control_read(0x55, 1).tostring()
            if camstat not in ('A', 'C'):
                raise CanonError('Some kind of init error, camstat: %s', camstat)

            msg = self.control_read(0x01, 0x58)
            if camstat == 'A':
                _log.debug("Camera was already active")
                self.control_read(0x04, 0x50)
                return camstat

        _log.debug("Camera woken up, initializing")
        msg[0:0x40] = array('B', [0]*0x40)
        msg[0] = 0x10
        msg[0x40:] = msg[-0x10:]
        self.control_write(0x11, msg)
        self.bulk_read(0x44)

        started = time.time()
        while len(p.received) < 0x10:
            time.sleep(0.2)
            if time.time() - started > 5.0:
                #raise CanonError("Waited for interrupt in data for too long!")
                _log.error("Waited for interrupt data for too long!!!")
                break

        cnt = 0
        while cnt < 4:
            cnt += 1
            try:
                commands.IdentifyCameraCmd().execute(self)
                return camstat
            except (USBError, CanonError), e:
                _log.debug("identify after init fails: {}".format(e))

        raise CanonError("identify_camera failed too many times")

    def control_read(self, wValue, data_length=0, timeout=None):
        # bRequest is 0x4 if length of data is >1, 0x0c otherwise (length >1 ? 0x04 : 0x0C)
        bRequest = 0x04 if data_length > 1 else 0x0c
        _log.info("control_read (req: 0x{:x} wValue: 0x{:x}) reading 0x{:x} bytes"
                   .format(bRequest, wValue, data_length))
        # bmRequestType is 0xC0 during read and 0x40 during write.
        response = self.device.ctrl_transfer(
                                 0xc0, bRequest, wValue=wValue, wIndex=0,
                                 data_or_wLength=data_length, timeout=timeout)
        if len(response) != data_length:
            raise CanonError("incorrect response length form camera")
        _log.debug('\n' + hexdump(response))
        return response

    def control_write(self, wValue, data='', timeout=None):
        # bRequest is 0x4 if length of data is >1, 0x0c otherwise (length >1 ? 0x04 : 0x0C)
        bRequest = 0x04 if len(data) > 1 else 0x0c
        _log.info("control_write (rt: 0x{:x}, req: 0x{:x}, wValue: 0x{:x}) 0x{:x} bytes"
                  .format(0x40, bRequest, wValue, len(data)))
        _log.debug("\n" + hexdump(data))
        # bmRequestType is 0xC0 during read and 0x40 during write.
        i = self.device.ctrl_transfer(0x40, bRequest, wValue=wValue, wIndex=0,
                                      data_or_wLength=data, timeout=timeout)
        if i != len(data):
            raise CanonError("control write was incomplete")
        return i

    def bulk_read(self, size, timeout=None):
        start = time.time()
        data = self.ep_in.read(size, timeout)
        end = time.time()
        data_size = len(data)
        if not data_size == size:
            _log.warn("bulk_read: WRONG SIZE: 0x{:x} bytes instead of 0x{:x}"
                      .format(data_size, size))
            _log.debug('\n' + hexdump(data))
            raise CanonError("unexpected data length ({} instead of {})"
                          .format(len(data), size))
        _log.info("bulk_read got {} (0x{:x}) b in {:.6f} sec"
                  .format(len(data), len(data), end-start))
        _log.debug("\n" + hexdump(data))
        return data

    def interrupt_read(self, size, timeout=100, ignore_timeouts=False):
        try:
            data = self.ep_int.read(size, timeout)
        except USBError, e:
            if ignore_timeouts and e.errno == 110:
                return array('B')
            raise
        if data is not None and len(data):
            dlen = len(data)
            _log.info("interrupt_read: got 0x{:x} bytes".format(dlen))
            _log.debug("\n" + hexdump(data))
            return data
        return array('B')

