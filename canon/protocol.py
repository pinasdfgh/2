# coding: utf-8
import struct
import threading
import itertools
import logging
from array import array

from canon import commands, CanonError
from canon.util import Bitfield, Flag, BooleanFlag, le32toi, hexdump, itole32a
import time
from usb.core import USBError
import usb.util
from contextlib import contextmanager

_log = logging.getLogger(__name__)

MAX_CHUNK_SIZE = 0x1400

class TransferMode(Bitfield):
    THUMB_TO_PC    = 0x01
    FULL_TO_PC     = 0x02
    THUMB_TO_DRIVE = 0x04
    FULL_TO_DRIVE  = 0x08

    pc = Flag(0, thumb=0x01, full=0x02)
    drive =  Flag(0, thumb=0x04, full=0x08)

class FSAttributes(Bitfield):

    _size = 0x01

    DOWNLOADED = 0x20
    WRITE_PROTECTED = 0x01
    RECURSE_DIR = 0x80
    NONRECURSE_DIR = 0x10

    UNKNOWN_2 = 0x02
    UNKNOWN_4 = 0x04
    UNKNOWN_8 = 0x08
    UNKNOWN_40 = 0x40

    recurse = BooleanFlag(0, true=RECURSE_DIR, false=NONRECURSE_DIR)
    downloaded = BooleanFlag(0, true=DOWNLOADED)
    protected = BooleanFlag(0, true=WRITE_PROTECTED)

    @property
    def is_dir(self):
        return (self.RECURSE_DIR in self.recurse
                    or self.NONRECURSE_DIR in self.recurse)

class FSEntry(object):
    def __init__(self, name, attributes, size=None, timestamp=None):
        self.name = name
        self.size = size
        self.timestamp = timestamp
        if not isinstance(attributes, FSAttributes):
            attributes = FSAttributes(attributes)
        self.attr = attributes
        self.children = []
        self.parent = None

    @property
    def full_path(self):
        if self.parent is None:
            return self.name
        return self.parent.full_path + '\\' + self.name
    @property
    def entry_size(self):
        return 11 + len(self.name)

    @property
    def type_(self):
        return 'd' if self.attr.is_dir else 'f'

    @property
    def is_dir(self):
        return self.attr.is_dir

    def __iter__(self):
        yield self
        for entry in itertools.chain(*self.children):
            yield entry

    def __repr__(self):
        return "<FSEntry {0.type_} '{0.full_path}'>".format(self)

    def __str__(self):
        return self.full_path

class CanonUSB(object):
    """Communicate with a Canon camera, old style.

    This may someday be used for another old Canon, not my G3. It should
    be as generic as possible. Code is heavily based on
    http://www.graphics.cornell.edu/~westin/canon/index.html
    and gphoto2's source.

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
                    chunk = self.usb._poll_interrupt(self.chunk, self.timeout)
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
                    if e.errno == 110: # timeout
                        continue

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
    def timeout_ctx(self, to):
        old = self.device.default_timeout
        self.device.default_timeout = to
        _log.info("timeout_ctx: {} -> {}".format(old, to))
        try:
            yield
        finally:
            _log.info("timeout_ctx: back to {}".format(old))
            self.device.default_timeout = old

    def poller(self, size=None, timeout=None):
        if self._poller:
            self._poller.stop()
        self._poller = self.InterruptPoller(self, size, timeout=timeout)
        self._poller.start()
        return self._poller

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
        except USBError as e:
            _log.debug("Will attempt to set configuration now, {}".format(e))
            self.device.set_configuration()
            self.device.set_interface_altsetting()

        for ep in (self.ep_in, self.ep_int, self.ep_out):
            try:
                usb.control.clear_feature(self.device, usb.control.ENDPOINT_HALT, ep)
            except USBError, e:
                _log.info("Clearing HALT on {} failed: {}".format(ep, e))

        p = self.poller()
        try:
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

            while len(p.received) < 0x10:
                time.sleep(0.2)

            cnt = 0
            while cnt < 4:
                cnt += 1
                try:
                    self.do_command(commands.IDENTIFY_CAMERA)
                    return camstat
                except (USBError, CanonError), e:
                    _log.debug("identify after init fails: {}".format(e))

            raise CanonError("identify_camera failed too many times")
        finally:
            p.stop()


    def _control_read(self, value, data_length=0, timeout=None):
        bRequest = 0x04 if data_length > 1 else 0x0c
        _log.info("CTRL IN (req: 0x{:x} wValue: 0x{:x}) reading 0x{:x} bytes"
                   .format(bRequest, value, data_length))
        response = self.device.ctrl_transfer(
                                 0xc0, bRequest, wValue=value, wIndex=0,
                                 data_or_wLength=data_length, timeout=timeout)
        if len(response) != data_length:
            raise CanonError("incorrect response length form camera")
        _log.debug('\n' + hexdump(response))
        return response

    def _control_write(self, wValue, data='', timeout=None):
        bRequest = 0x04 if len(data) > 1 else 0x0c
        _log.info("CTRL OUT (rt: 0x{:x}, req: 0x{:x}, wValue: 0x{:x}) 0x{:x} bytes"
                  .format(0x40, bRequest, wValue, len(data)))
        _log.debug("\n" + hexdump(data))
        i = self.device.ctrl_transfer(0x40, bRequest, wValue=wValue, wIndex=0,
                                      data_or_wLength=data, timeout=timeout)
        if i != len(data):
            raise CanonError("control write incomplete")
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

    def _poll_interrupt(self, size, timeout=100):
        data = self.ep_int.read(size, timeout)
        if data is not None and len(data):
            _log.info("Interrupt got {} bytes".format(len(data)))
            _log.debug("\n" + hexdump(data))
            return data
        return array('B')

    def _get_packet(self, cmd, payload):
        payload_length = len(payload) if payload else 0
        request_size = array('B', struct.pack('<I', payload_length + 0x10))
        self._cmd_serial += (self._cmd_serial % 4) + 1 # just playin'
        if self._cmd_serial > 65535: self._cmd_serial = 0
        serial = array('B', struct.pack('<I', self._cmd_serial))
        serial[2] = 0x12

        # what we dump on the pipe
        packet = array('B', [0] * 0x50) # 80 byte command block

        packet[0:4] = request_size
        packet[0x40] = 2 # just works, gphoto2 does magic for other camera classes
        packet[0x44] = cmd['cmd1'];
        packet[0x47] = cmd['cmd2'];
        packet[4:8] = array('B', struct.pack('<I', cmd['cmd3']))
        packet[0x48:0x48+4] = request_size # again
        packet[0x4c:0x4c+4] = serial

        if payload is not None:
            packet.extend(array('B', payload))

        return packet

    def do_command_iter(self, cmd, payload=None, full=False):
        """Run a command on the camera.

        TODO: this
        """
        packet = self._get_packet(cmd, payload)
        _log.info("{0[c_idx]:s} (0x{0[cmd1]:x}, 0x{0[cmd2]:x}, 0x{0[cmd3]:x}), "
                  "retlen 0x{0[return_length]:x} #{1:0}"
                  .format(cmd, self._cmd_serial))

        self._control_write(0x10, packet)

        # the response
        # always read first chunk if return_length says so
        total_read = int(cmd['return_length'])
        if total_read > MAX_CHUNK_SIZE:
            first_read = MAX_CHUNK_SIZE
        elif total_read > 0x40:
            first_read = (int(total_read) / 0x40) * 0x40
        else:
            first_read = total_read
        remainder_read = total_read - first_read

        data = self._bulk_read(first_read)

        if cmd['cmd3'] == 0x202:
            # variable-length response
            resp_len = le32toi(data[6:10])
            _log.debug("variable response says 0x%x bytes follow",
                      resp_len)
            remainder_read = resp_len
        else:
            reported_read = le32toi(data[0:4]) + 0x40
            if reported_read != total_read:
                _log.warn("bad response length, reported 0x{:x} vs. 0x{:x}"
                          .format(reported_read, total_read))
                remainder_read = reported_read - first_read
            else:
                _log.info("first chunk 0x{:x}, 0x{:x} to go, 0x{:x} reported"
                          .format(first_read, remainder_read, reported_read))

        if full:
            yield data[:0x40]

        data = data[0x40:]

        if len(data) >= 0x14:
            status = le32toi(data, 0x10)
            _log.info("{0[c_idx]:s} #{1:0} : status {2:x}"
                      .format(cmd, self._cmd_serial, status))
        if len(data):
            yield data

        _log.debug("Chunked read of 0x{:x} bytes".format(remainder_read))
        read = 0
        while read < remainder_read:
            remaining = remainder_read - read
            if remaining > MAX_CHUNK_SIZE:
                chunk_size = MAX_CHUNK_SIZE
            elif remaining > 0x40:
                chunk_size = remaining - (remaining % 0x40)
            else:
                chunk_size = remaining

            _log.debug("chunked reading 0x{:x}".format(chunk_size))
            data = self._bulk_read(chunk_size)
            if len(data) != chunk_size:
                raise CanonError("unable to read requested data")

            if read <= 0x10 and (chunk_size + read) >= 0x14:
                status = le32toi(data, 0x10-read)
                _log.info("{0[c_idx]:s} #{1:0} : status {2:x}"
                          .format(cmd, self._cmd_serial, status))

            read += chunk_size
            yield data

    def do_command(self, cmd, payload=None, full=False):
        data = array('B')
        for chunk in self.do_command_iter(cmd, payload, full):
            data.extend(chunk)
        #        expected = first_read + remainder_read
        #        if expected != actual_read:
        #            raise CanonError("didn't get expected response length, "
        #                          " expected %s (0x%x) but got %s (0x%x)" % (
        #                             expected, expected, actual_read, actual_read))
        # TODO: implement the check gphoto2 does when it sees the camera
        #       reporting a return_length different than the expected for
        #       this command.
        #if len(data) >= 0x50:
        #    reported_len = struct.unpack('<I', data[0x48:0x48+4].tostring())
        #    if reported_len != len(data):
        #        import warnings; warnings.warn()
        _log.info("{0[c_idx]:s} #{1:0} -> 0x{2:x} bytes".format(
                                          cmd, self._cmd_serial, len(data)))
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
            payload = array('B', struct.pack('<I', rc_cmd['value']))
            if arg1 is None: arg1 = 0x00
            payload.extend(itole32a(arg1))
            if arg2 is not None:
                payload.extend(itole32a(arg2))
        return self.do_command(cmd, payload, True)

