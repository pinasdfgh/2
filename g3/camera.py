import sys
import os
import logging
import struct
import itertools
from array import array

import usb.core
import usb.util
import usb.control
from usb.core import USBError

from g3 import commands
from g3.util import extract_string, le32toi, itole32a, hexdump
import time

_log = logging.getLogger(__name__)

MAX_CHUNK_SIZE = 0x1400

class G3Error(Exception): pass

class FSAttributes(object):

    RECURSE_DIR = 0x80
    NONRECURSE_DIR = 0x10

    def __init__(self, value):
        self.value = value

    @property
    def is_dir(self):
        return ((self.value & self.RECURSE_DIR)
                    or (self.value & self.NONRECURSE_DIR))



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
    def type(self):
        return 'd' if self.attr.is_dir else 'f'

    def __iter__(self):
        yield self
        for x in itertools.chain(*self.children):
            yield x

    def __repr__(self):
        return "<FSEntry {0.type} '{0.full_path}'>".format(self)

    def __str__(self):
        return self.full_path

class CanonUSB(object):
    """Communicate with a Canon camera, old style.

    It is possible that this is someday used for another old Canon,
    not my G3. It should be as generic as possible. Code is heavily based on
    http://www.graphics.cornell.edu/~westin/canon/index.html
    and gphoto2's source.

    """
    def __init__(self, device):
        self.device = device
        self.iface = iface = device[0][0,0]

        # Other models may have different EP addresses
        self.ep_in = usb.util.find_descriptor(iface, bEndpointAddress=0x81)
        self.ep_out = usb.util.find_descriptor(iface, bEndpointAddress=0x02)
        self.ep_int = usb.util.find_descriptor(iface, bEndpointAddress=0x83)
        self._cmd_serial = 0

    def is_ready(self):
        """Check if the camera has been initialized by issuing IDENTIFY_CAMERA.

        gphoto2 source claims that this command does not change the state
        of the camera and can safely be issued without any side effects.
        """
        try:
            self.do_command(commands.IDENTIFY_CAMERA)
            return True
        except (USBError, G3Error):
            return False

    def initialize(self):
        """Bring the camera into a state where it accepts commands.
        """
        try:
            cfg = self.device.get_active_configuration()
            _log.debug("Configuration %s already set.", cfg.bConfigurationValue)
        except USBError, e:
            _log.debug("Will configure device now.")
            self.device.set_configuration()
            self.device.set_interface_altsetting()

        try:
            usb.control.clear_feature(self.device, usb.control.ENDPOINT_HALT, self.ep_in)
            usb.control.clear_feature(self.device, usb.control.ENDPOINT_HALT, self.ep_out)
            usb.control.clear_feature(self.device, usb.control.ENDPOINT_HALT, self.ep_int)
        except USBError, e:
            _log.info("Clearing HALTs failed: %s", e)

        # do the init dance
        camstat = self._control_read(0x55, 1).tostring()
        if camstat not in ('A', 'C'):
            raise G3Error('Some kind of init error, camstat: %s', camstat)

        msg = self._control_read(0x01, 0x58)
        if camstat == 'A':
            _log.debug("Camera was already active")
            self._control_read(0x04, 0x50)
            return camstat

        _log.debug("Camera woken up, initializing")
        msg[0:0x40] = array('B', [0 for _ in range(0x40)])
        msg[0] = 0x10
        msg[0x40:] = msg[-0x10:]
        self._control_write(0x11, msg)
        self.ep_in.read(0x44)

        read = 0
        read += len(self._poll_interrupt(0x10))
        while read < 0x10:
            time.sleep(0.02)
            read += len(self._poll_interrupt(0x10))

        cnt = 0
        while True:
            try:
                self.do_command(commands.IDENTIFY_CAMERA)
                return
            except (USBError, G3Error):
                cnt += 1
                if cnt >=4:
                    raise G3Error("identify_camera failed too many times")

        return camstat

    def _control_read(self, value, data_length=0, timeout=None):
        bRequest = 0x04 if data_length > 1 else 0x0c
        response = self.device.ctrl_transfer(
                                 0xc0, bRequest, wValue=value, wIndex=0,
                                 data_or_wLength=data_length, timeout=timeout)
        if len(response) != data_length:
            raise G3Error("incorrect response length form camera")
        _log.info("_control_read %x{:x}", len(response))
        _log.debug(hexdump(response))
        return response

    def _control_write(self, wValue, data='', timeout=None):
        bRequest = 0x04 if len(data) > 1 else 0x0c
        _log.info("_control_write(0x%x, 0x%x, 0x%x, 0x%x)",
                  0x40, bRequest, wValue, 0)
        i = self.device.ctrl_transfer(0x40, bRequest, wValue=wValue, wIndex=0,
                                      data_or_wLength=data, timeout=timeout)
        if i != len(data):
            raise G3Error("control write incomplete")
        return i

    def _bulk_read(self, size, timeout=500):
        data = self.ep_in.read(size, timeout)
        if not len(data) == size:
            raise G3Error("unexpected data length (%s instead of %s)",
                          len(data), size)
        _log.info("_bulk_read got %s (0x%x)" % (len(data), len(data)))
        _log.debug(hexdump(data))
        return data

    def _poll_interrupt(self, size, timeout=500):
        data = self.ep_int.read(size, timeout)
        if len(data):
            _log.debug("interrupt pipe yielded %s bytes:\n%s", len(data),
                       hexdump(data))
        return data

    def _construct_packet(self, cmd, payload):
        payload_length = len(payload) if payload else 0
        request_size = array('B', struct.pack('<I', payload_length + 0x10))
        self._cmd_serial += 1
        serial = self._cmd_serial

        # what we dump on the pipe
        packet = array('B', [0] * 0x50) # 80 byte command block
        packet[0:4] = request_size
        packet[0x40] = 2 # just works this way
        packet[0x44] = cmd['cmd1'];
        packet[0x47] = cmd['cmd2'];
        packet[4:8] = array('B', struct.pack('<I', cmd['cmd3']))
        packet[0x4c:0x4c+4] = array('B', struct.pack('<I', serial))
        packet[0x48:0x48+4] = request_size # again

        if payload is not None:
            packet.extend(array('B', payload))

        return packet

    def do_command_iter(self, cmd, payload=None, full=False):
        """Run a command on the camera.

        TODO: this
        """
        packet = self._construct_packet(cmd, payload)
        _log.info("{0[c_idx]:s} (0x{0[cmd1]:x}, 0x{0[cmd2]:x}, 0x{0[cmd3]:x}, "
                  "retlen 0x{0[return_length]:x} #{1:0}"
                  .format(cmd, self._cmd_serial))

        self._control_write(0x10, packet)

        # the response
        # always read first chunk if return_length says so
        total_read = int(cmd['return_length'])
        first_read = 0x40
        remainder_read = total_read - first_read

        data = self._bulk_read(first_read)
        if cmd['cmd3'] == 0x202:
            # variable-length response
            resp_len = le32toi(data[6:10])
            _log.debug("variable response says 0x%x bytes follow",
                      resp_len)
            remainder_read = resp_len
        else:
            _log.info("first chunk 0x{:x}, 0x{:x} follow".format(
                             first_read, remainder_read))

        if full:
            yield data

        for data_chunk in self._chunked_read(remainder_read):
            yield data_chunk

    def _chunked_read(self, size, chunk=MAX_CHUNK_SIZE, timeout=500):
        read = 0
        while read < size:
            remaining = size - read
            if remaining > chunk:
                chunk_size = chunk
            elif remaining > 0x40:
                chunk_size = remaining - (remaining % 0x40)
            else:
                chunk_size = remaining
            data = self._bulk_read(chunk_size)
            if len(data) != chunk_size:
                raise G3Error("unable to read requested data")
            read += chunk_size
            yield data

    def do_command(self, cmd, payload=None, full=False):
        data = array('B')
        for chunk in self.do_command_iter(cmd, payload, full):
            data.extend(chunk)
        #        expected = first_read + remainder_read
        #        if expected != actual_read:
        #            raise G3Error("didn't get expected response length, "
        #                          " expected %s (0x%x) but got %s (0x%x)" % (
        #                             expected, expected, actual_read, actual_read))
        # TODO: implement the check gphoto2 does when it sees the camera
        #       reporting a return_length different than the expected for
        #       this command.
        #if len(data) >= 0x50:
        #    reported_len = struct.unpack('<I', data[0x48:0x48+4].tostring())
        #    if reported_len != len(data):
        #        import warnings; warnings.warn()
        _log.debug("{0[c_idx]:s} #{1:0} -> 0x{2:x} bytes".format(
                                          cmd, self._cmd_serial, len(data)))
        return data


    def do_command_rc(self, rc_cmd, arg1=None, arg2=None):
        """Do a remote-control command

        See http://www.graphics.cornell.edu/~westin/canon/ch03s18.html
        """
        old_timeout, self.device.default_timeout = self.device.default_timeout, 15000
        cmd = commands.CONTROL_CAMERA.copy()
        cmd['return_length'] += rc_cmd['return_length']
        payload = array('B', struct.pack('<I', rc_cmd['value']))
        if arg1 is None: arg1 = 0x00
        if arg2 is None: arg2 = 0x00

        payload.extend(array('B', [arg1, arg2]))
        try:
            return self.do_command(cmd, payload, True)
        finally:
            self.device.default_timeout = old_timeout

class Camera(object):

    VENDORID = 0x04a9
    PRODUCTID = 0x306e

    @classmethod
    def find(cls):
        dev = usb.core.find(idVendor=cls.VENDORID, idProduct=cls.PRODUCTID)
        if not dev:
            _log.debug("Unable to find a Canon G3 camera attached to this host")
            return None
        _log.info("Found a Canon G3 on bus %s address %s", dev.bus, dev.address)
        return cls(dev)

    def __init__(self, device):
        self.device = device
        self.usb = CanonUSB(device)
        self._in_rc = False

    def initialize(self):
        if not self.is_ready():
            _log.info("initialize called, but camera seems up")
            return self.usb.initialize()

    def is_ready(self):
        try:
            return bool(self.identify())
        except (USBError, G3Error):
            return False

    def identify(self):
        """ -> (model, owner, version) strings
        """
        data = self.usb.do_command(commands.IDENTIFY_CAMERA, full=False)
        model = extract_string(data, 0x1c)
        owner = extract_string(data, 0x3c)
        version = '.'.join([str(x) for x in data[0x1b:0x18:-1]])
        return model, owner, version

    def set_time(self, new_date=None):
        """Set the current date and time
        """
        if new_date is None:
            # TODO: convert to local tz, accept datetime
            new_date = time.time()
        new_date = int(new_date)
        self.usb.do_command(commands.SET_TIME, itole32a(new_date))
        return self.get_time()

    def get_time(self):
        """Get the current date and time
        """
        resp = self.usb.do_command(commands.GET_TIME, full=False)
        return le32toi(resp[4:8])

    def get_drive(self):
        resp = self.usb.do_command(commands.FLASH_DEVICE_IDENT, full=False)
        return extract_string(resp)

    def ls(self, path=None, recurse=12):
        """Return an FSEntry for the path, storage root by default.
        """
        path = self._normalize_path(path)
        payload = array('B', [recurse])
        payload.extend(array('B', path))
        payload.extend(array('B', [0x00] * 3))
        data = self.usb.do_command(commands.GET_DIR, payload, False)

        def extract_entry(data):
            idx = 0
            while True:
                name = extract_string(data, idx+10)
                if not name:
                    raise StopIteration()
                entry = FSEntry(name, attributes=data[idx],
                                size=le32toi(data[idx+2:idx+6]),
                                timestamp=le32toi(data[idx+6:idx+10]))
                idx += entry.entry_size
                yield entry

        entry_generator = iter(extract_entry(data))
        root = entry_generator.next()
        current = root
        while True:
            try:
                entry = entry_generator.next()
            except StopIteration:
                return root
            if entry.name == '..':
                current = current.parent
                continue
            current.children.append(entry)
            entry.parent = current
            if entry.name.startswith('.\\'):
                entry.name = entry.name[2:]
                current = entry
            _log.info(entry)

    def get_file(self, path, target, thumbnail=False):
        if not hasattr('write', target):
            target = open(target, 'wb+')
        payload = array('B', [0x00]*8)
        payload[0] = 0x01 if thumbnail else 0x00
        payload[4:8] = itole32a(MAX_CHUNK_SIZE)
        payload.extend(array('B', self._normalize_path(path)))
        payload.append(0x00)
        with target:
            for chunk in self.usb.do_command_iter(commands.GET_FILE, payload):
                target.write(chunk.tostring())

    def rc_start(self):
        self.usb._poll_interrupt(0x10)

        old_timeout, self.device.default_timeout = self.device.default_timeout, 15000
        data = self.usb.do_command_rc(commands.RC_INIT)
        self.device.default_timeout = old_timeout
        return data

    def rc_stop(self):
        old_timeout, self.device.default_timeout = self.device.default_timeout, 10000
        data = self.usb.do_command_rc(commands.RC_EXIT)
        self.device.default_timeout = old_timeout
        return data

    def _normalize_path(self, path):
        drive = self.get_drive()
        if path is None:
            path = ''
        if isinstance(path, FSEntry):
            path = path.full_path
        if not path.startswith(drive):
            path = '\\'.join([drive, path]).rstrip('\\')
        return path


#    def capture_(self):
#        """
#        canon_int_capture_image()
#            canon_int_start_remote_control()
#                canon_int_do_control_command(CANON_USB_CONTROL_INIT, 0, 0);
#
#            canon_int_do_control_command(CANON_USB_CONTROL_SET_TRANSFER_MODE,
#                                           0x04, transfermode);
#            canon_int_do_control_command(CANON_USB_CONTROL_GET_PARAMS, 0x00, 0);
#            canon_int_do_control_command(CANON_USB_CONTROL_GET_PARAMS, 0x04, transfermode);
#            /* Shutter Release
#               Can't use normal "canon_int_do_control_command", as
#               we must read the interrupt pipe before the response
#               comes back for this commmand. */
#            canon_usb_capture_dialogue(&return_length, &photo_status, context );
#        """
