import sys
import os
import logging
import struct
from array import array

import usb.core
import usb.util
import usb.control
from usb.core import USBError

from g3 import commands
from g3.util import extract_string, le32toi, itole32a, dumphex
import time

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)
_log.addHandler(logging.StreamHandler())
logging.getLogger('usb').addHandler(logging.StreamHandler(sys.stderr))

class G3Error(Exception): pass

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
        try:
            self.canon_dialogue(commands.IDENTIFY_CAMERA)
            return True
        except (USBError, G3Error):
            return False

    def initialize(self):
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
            pass

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
                self.canon_dialogue(commands.IDENTIFY_CAMERA)
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
        _log.debug("_control_read got\n" + dumphex(response))
        return response

    def _control_write(self, wValue, data='', timeout=None):
        bRequest = 0x04 if len(data) > 1 else 0x0c
        _log.debug("_control_write(0x%x, 0x%x, 0x%x, 0x%x):\n%s",
                   0x40, bRequest, wValue, 0, dumphex(data) or 'None')
        i = self.device.ctrl_transfer(0x40, bRequest, wValue=wValue, wIndex=0,
                                      data_or_wLength=data, timeout=timeout)
        if i != len(data):
            raise G3Error("control write incomplete")
        return i

    def _bulk_read(self, size):
        data = self.ep_in.read(size)
        if not len(data) == size:
            raise G3Error("unexpected data length (%s instead of %s)",
                          len(data), size)
        _log.debug("_bulk_read got %s bytes:\n%s" % (len(data), dumphex(data)))
        return data

    def _poll_interrupt(self, size, timeout=500):
        data = self.ep_int.read(size, timeout)
        if len(data):
            _log.debug("interrupt pipe yielded %s bytes:\n%s", len(data),
                       dumphex(data))
        return data

    def canon_dialogue(self, cmd, payload=None):
        _log.debug(("%(c_idx)s (0x%(cmd1)x, 0x%(cmd2)x, 0x%(cmd3)x), "
                    "expecting %(return_length)s bytes") % cmd)

        payload_length = len(payload) if payload else 0
        request_size = array('B', struct.pack('<I', payload_length + 0x10))

        # what we dump on the pipe
        packet = array('B', [0] * 0x50)

        packet[0:4] = request_size
        packet[0x40] = 2 # just works this way
        packet[0x44] = cmd['cmd1'];
        packet[0x47] = cmd['cmd2'];
        packet[4:8] = array('B', struct.pack('<I', cmd['cmd3']))
        packet[0x4c:0x4c+4] = array('B', struct.pack('<I', self._cmd_serial))
        self._cmd_serial += 1
        packet[0x48:0x48+4] = request_size # again

        if payload is not None:
            packet.extend(array('B', payload))

        self._control_write(0x10, packet)

        # the response
        # always read first chunk if return_length says so
        total_read = int(cmd['return_length'])
        remainder_read = total_read % 0x40
        first_read = total_read - remainder_read
        _log.debug("response in chunks of 0x%x and 0x%x", first_read,
                   remainder_read)

        data = self._bulk_read(first_read)

        if cmd['cmd3'] == 0x202:
            # variable-length response, read the lenght and
            # read the rest of the response nicely chunked
            # or do we...
            resp_len = le32toi(data[6:10])
            data = array('B')
            while len(data) < resp_len:
                remaining = resp_len - len(data)
                if remaining > 0x1400:
                    chunk_size = 0x1400
                elif remaining > 0x40:
                    chunk_size = remaining - (remaining % 0x40)
                else:
                    chunk_size = remaining
                chunk = self.ep_in.read(chunk_size)
                if len(chunk) != chunk_size:
                    raise G3Error("unable to read requested data")
                data.extend(chunk)

            return data

        if remainder_read:
            data.extend(self._bulk_read(remainder_read))

        if len(data) != cmd['return_length']:
            raise G3Error("didn't get expected number of bytes in response")

#        if len(data) >= 0x50:
#            reported_len = struct.unpack('<I', data[0x48:0x48+4].tostring())
#            if reported_len != len(data):
#                import warnings; warnings.warn()

        return data

    def canon_dialogue_stripped(self, cmd, payload=None):
        data = self.canon_dialogue(cmd, payload)
        return data[0x50:]

    def canon_dialogue_rc(self, rc_cmd, arg1=None, arg2=None):
        """Conduct an in-remote-control command."""
        old_timeout, self.device.default_timeout = self.device.default_timeout, 15000
        cmd = commands.CONTROL_CAMERA.copy()
        cmd['return_length'] += rc_cmd['return_length']
        payload = array('B', struct.pack('<I', rc_cmd['value']))
        if arg1 is None: arg1 = 0x00
        if arg2 is None: arg2 = 0x00

        payload.extend(array('B', [arg1, arg2]))
        try:
            return self.canon_dialogue(cmd, payload)
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

    def initialize(self):
        if not self.is_ready():
            _log.info("initialize called, but camera seems up")
            return self.usb.initialize()

    def is_ready(self):
        try:
            return bool(self.identify_camera())
        except (USBError, G3Error):
            return False

    def identify_camera(self):
        data = self.usb.canon_dialogue(commands.IDENTIFY_CAMERA)
        model = extract_string(data, 0x5c)
        owner = extract_string(data, 0x7c)
        version = '.'.join([str(x) for x in data[0x5b:0x58:-1]])
        return model, owner, version

    def set_time(self, new_date=None):
        if new_date is None:
            # TODO: convert to local tz, accept datetime
            new_date = time.time()
        new_date = int(new_date)
        self.usb.canon_dialogue(commands.SET_TIME, itole32a(new_date))
        return self.get_time()

    def get_time(self):
        resp = self.usb.canon_dialogue_stripped(commands.GET_TIME)
        return le32toi(resp[4:8])

    def rc_start(self):
#        while True:
#            read = self.ep_int.read(0x10)
#            if not len(read):
#                _log.debug("No more data on the INT endpoint")
#                break
#            _log.debug("Got %s bytes from INT endpoint", len(read))

        old_timeout, self.device.default_timeout = self.device.default_timeout, 15000
        data = self.usb.canon_dialogue_rc(commands.RC_INIT)
        self.device.default_timeout = old_timeout
        return data

    def rc_stop(self):
        old_timeout, self.device.default_timeout = self.device.default_timeout, 10000
        data = self.usb.canon_dialogue_rc(commands.RC_EXIT)
        self.device.default_timeout = old_timeout
        return data

    def capture_(self):
        """
        canon_int_capture_image()
            canon_int_start_remote_control()
                canon_int_do_control_command(CANON_USB_CONTROL_INIT, 0, 0);

            canon_int_do_control_command(CANON_USB_CONTROL_SET_TRANSFER_MODE,
                                           0x04, transfermode);
            canon_int_do_control_command(CANON_USB_CONTROL_GET_PARAMS, 0x00, 0);
            canon_int_do_control_command(CANON_USB_CONTROL_GET_PARAMS, 0x04, transfermode);
            /* Shutter Release
               Can't use normal "canon_int_do_control_command", as
               we must read the interrupt pipe before the response
               comes back for this commmand. */
            canon_usb_capture_dialogue(&return_length, &photo_status, context );



        """

