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


import time
import threading
import logging
from array import array
from contextlib import contextmanager

from usb.core import USBError
import usb.util

from canon import commands, CanonError
from canon.util import le32toi, hexdump, itole32a, Bitfield

_log = logging.getLogger(__name__)

MAX_CHUNK_SIZE = 0x1400

class CanonUSB(object):
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

    class InterruptPoller(threading.Thread):
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
                    chunk = self.usb.poll_interrupt(self.chunk, self.timeout)
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
                        _log.warn("poll: {}".format(e))
                        return
                    _log.warn("poll: {}".format(e))
                    errors += 1
            _log.info("poller got too many errors, exiting")

        def stop(self):
            self.should_stop = True
            self.join()

    def __init__(self, device):
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
        _log.info("timeout_ctx: {} -> {}".format(old, new))
        now = time.time()
        try:
            yield
        finally:
            _log.info("timeout_ctx: {} <- {}; back in {:.5f} s"
                      .format(old, new, time.time() - now))
            self.device.default_timeout = old

    @contextmanager
    def poller(self, size=None, timeout=None):
        if self._poller:
            self._poller.stop()
        self._poller = self.InterruptPoller(self, size, timeout=timeout)
        self._poller.start()
        yield self._poller
        self._poller.stop()

    def is_ready(self):
        """Check if the camera has been initialized by issuing IDENTIFY_CAMERA.

        gphoto2 source claims that this command doesn't change the state
        of the camera and can safely be issued without any side effects.

        """
        try:
            self.do_command(commands.IDENTIFY_CAMERA)
            return True
        except (USBError, CanonError):
            return False

    ready = property(is_ready)

    def initialize(self):
        """Bring the camera into a state where it accepts commands.
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

        with self.poller() as p:
            # do the init dance
            with self.timeout_ctx(5000):
                camstat = self._control_read(0x55, 1).tostring()
                if camstat not in ('A', 'C'):
                    raise CanonError('Some kind of init error, camstat: %s', camstat)

                msg = self._control_read(0x01, 0x58)
                if camstat == 'A':
                    _log.debug("Camera was already active")
                    self._control_read(0x04, 0x50)
                    return camstat

            _log.debug("Camera woken up, initializing")
            msg[0:0x40] = array('B', [0]*0x40)
            msg[0] = 0x10
            msg[0x40:] = msg[-0x10:]
            self._control_write(0x11, msg)
            self._bulk_read(0x44)

            started = time.time()
            while len(p.received) < 0x10:
                time.sleep(0.2)
                if time.time() - started > 5.0:
                    raise CanonError("Waited for interrupt in data for too long!")

            cnt = 0
            while cnt < 4:
                cnt += 1
                try:
                    self.do_command(commands.IDENTIFY_CAMERA)
                    return camstat
                except (USBError, CanonError), e:
                    _log.debug("identify after init fails: {}".format(e))

            raise CanonError("identify_camera failed too many times")

    def _control_read(self, wValue, data_length=0, timeout=None):
        # bRequest is 0x4 if length of data is >1, 0x0c otherwise (length >1 ? 0x04 : 0x0C)
        bRequest = 0x04 if data_length > 1 else 0x0c
        _log.info("CTRL IN (req: 0x{:x} wValue: 0x{:x}) reading 0x{:x} bytes"
                   .format(bRequest, wValue, data_length))
        # bmRequestType is 0xC0 during read and 0x40 during write.
        response = self.device.ctrl_transfer(
                                 0xc0, bRequest, wValue=wValue, wIndex=0,
                                 data_or_wLength=data_length, timeout=timeout)
        if len(response) != data_length:
            raise CanonError("incorrect response length form camera")
        _log.debug('\n' + hexdump(response))
        return response

    def _control_write(self, wValue, data='', timeout=None):
        # bRequest is 0x4 if length of data is >1, 0x0c otherwise (length >1 ? 0x04 : 0x0C)
        bRequest = 0x04 if len(data) > 1 else 0x0c
        _log.info("CTRL OUT (rt: 0x{:x}, req: 0x{:x}, wValue: 0x{:x}) 0x{:x} bytes"
                  .format(0x40, bRequest, wValue, len(data)))
        _log.debug("\n" + hexdump(data))
        # bmRequestType is 0xC0 during read and 0x40 during write.
        i = self.device.ctrl_transfer(0x40, bRequest, wValue=wValue, wIndex=0,
                                      data_or_wLength=data, timeout=timeout)
        if i != len(data):
            raise CanonError("control write was incomplete")
        return i

    def _bulk_read(self, size, timeout=None):
        start = time.time()
        data = self.ep_in.read(size, timeout)
        end = time.time()
        data_size = len(data)
        if not data_size == size:
            _log.warn("BAD bulk in 0x{:x} bytes instead of 0x{:x}"
                      .format(data_size, size))
            _log.debug('\n' + hexdump(data))
            raise CanonError("unexpected data length ({} instead of {})"
                          .format(len(data), size))
        _log.info("bulk in got {} (0x{:x}) b in {:.6f} sec"
                  .format(len(data), len(data), end-start))
        _log.debug("\n" + hexdump(data))
        return data

    def poll_interrupt(self, size, timeout=100, ignore_timeouts=False):
        try:
            data = self.ep_int.read(size, timeout)
        except USBError, e:
            if ignore_timeouts and e.errno == 110:
                return array('B')
            raise
        if data is not None and len(data):
            dlen = len(data)
            _log.info("poll_interrupt got {} 0x{:x} bytes".format(dlen, dlen))
            _log.debug("\n" + hexdump(data))
            return data
        return array('B')

    def _get_packet(self, cmd, payload):
        """ -> array('B') of len=(0x50 + len(payload))
                  with canon usb header values set
        """
        payload_length = len(payload) if payload else 0
        request_size = itole32a(payload_length + 0x10)

        self._cmd_serial += ((self._cmd_serial % 8)) or 5 # just playin'
        if self._cmd_serial > 65530:
                self._cmd_serial = 0
        serial = itole32a(self._cmd_serial)
        serial[2] = 0x12

        # what we dump on the pipe
        packet = array('B', [0] * 0x50) # 80 byte command block

        packet[0:4] = request_size
        # just works, gphoto2 does magic for other camera classes
        packet[0x40] = 0x02
        packet[0x44] = cmd['cmd1']
        packet[0x47] = cmd['cmd2']
        packet[4:8] = itole32a(cmd['cmd3'])
        packet[0x48:0x48+4] = request_size # again
        packet[0x4c:0x4c+4] = serial

        if payload is not None:
            packet.extend(array('B', payload))

        return packet

    def do_command_iter(self, cmd, payload=None, full=False):
        """Run a command on the camera.
        """
        packet = self._get_packet(cmd, payload)
        _log.info(">>> {0[c_idx]:s} (0x{0[cmd1]:x}, 0x{0[cmd2]:x}, "
                  "0x{0[cmd3]:x}), retlen 0x{0[return_length]:x} #{1:0}"
                  .format(cmd, self._cmd_serial))

        def next_chunk_size(remaining):
            if remaining > MAX_CHUNK_SIZE:
                return MAX_CHUNK_SIZE
            elif remaining > 0x40:
                return (remaining // 0x40) * 0x40
            else:
                return remaining

        # always read at least one chunk
        # first_chunk_len is almost always 0x40
        if cmd['cmd3'] == 0x202:
            total_len = first_chunk_len = 0x40
        else:
            total_len = int(cmd['return_length'])
            first_chunk_len = next_chunk_size(total_len)
            remaining_len = total_len - first_chunk_len

        # control out, then bulk in the first chunk
        self._control_write(0x10, packet)
        data = self._bulk_read(first_chunk_len)

        def reader(bytes_to_yield):
            "iterator over the response data from bulk in"
            if full: # yield the first 0x40 bytes
                yield data[:0x40]
            if len(data) > 0x40:
                yield data[0x40:]
            bytes_yielded = 0
            while bytes_yielded < bytes_to_yield:
                chunk_len = next_chunk_size(bytes_to_yield - bytes_yielded)
                yield self._bulk_read(chunk_len)
                bytes_yielded += chunk_len

        # variable-length response
        # word at 0x06 is response length excluding the first 0x40
        if cmd['cmd3'] == 0x202:
            resp_len = le32toi(data[6:10])
            _log.debug("variable response says 0x%x bytes follow",
                      resp_len)
            _log.info("<<< {0[c_idx]:s} (0x{0[cmd1]:x}, 0x{0[cmd2]:x}, "
                      "0x{0[cmd3]:x}), retlen 0x{1:x} #{2:0}"
                      .format(cmd, resp_len + 0x40, self._cmd_serial))
            return reader(resp_len)

        # fixed-length response
        if len(data) < 0x4c:
            # need another chunk to get to the response length
            chunk_len = next_chunk_size(remaining_len)
            data.extend(self._bulk_read(chunk_len))
            remaining_len -= chunk_len
            assert len(data) >= 0x54
        # word at 0x48 is response length excluding the first 0x40
        resp_len = le32toi(data[0x48:0x4c])
        if resp_len + 0x40 != total_len:
            _log.warn("BAD resp_len, correcting 0x{:x} to 0x{:x} "
                      .format(total_len, resp_len))
            remaining_len = resp_len + 0x40 - len(data)
        # word at 0x50 is status byte
        status = le32toi(data, 0x50)
        _log.info("<<< {0[c_idx]:s} (0x{0[cmd1]:x}, 0x{0[cmd2]:x}, "
                  "0x{0[cmd3]:x}), retlen 0x{1:x} #{2:0} status 0x{3:0x}"
                  .format(cmd, resp_len + 0x40, self._cmd_serial,
                          status))
        return reader(remaining_len)

    def do_command(self, cmd, payload=None, full=False):
        data = array('B')
        for chunk in self.do_command_iter(cmd, payload, full):
            data.extend(chunk)
        return data


    def do_command_rc(self, rc_cmd, arg1=None, arg2=None, payload=None):
        """Do a remote-control command

        See http://www.graphics.cornell.edu/~westin/canon/ch03s18.html
        """
        assert not ((payload is not None) and (arg1 is not None))
        cmd = commands.CONTROL_CAMERA.copy()
        cmd['return_length'] += rc_cmd['return_length']
        _log.info("RC {0[c_idx]:s} retlen 0x{0[return_length]:x}"
                  .format(rc_cmd, cmd))
        if payload is None:
            payload = itole32a(rc_cmd['value'])
            if arg1 is None: arg1 = 0x00
            payload.extend(itole32a(arg1))
            if arg2 is not None:
                payload.extend(itole32a(arg2))
        return self.do_command(cmd, payload, True)

