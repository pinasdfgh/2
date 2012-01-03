import sys
import os
import logging
import struct
from array import array

import usb.core
import usb.util
import usb.control

from g3 import commands
from g3.util import extract_string
from usb.core import USBError

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)
_log.addHandler(logging.StreamHandler())
logging.getLogger('usb').addHandler(logging.StreamHandler(sys.stderr))

class G3Error(Exception): pass

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

    def __init__(self, dev):
        self.dev = dev
        self.iface = iface = dev[0][0,0]
        self.ep_in = usb.util.find_descriptor(iface, bEndpointAddress=0x81)
        self.ep_out = usb.util.find_descriptor(iface, bEndpointAddress=0x02)
        self.ep_int = usb.util.find_descriptor(iface, bEndpointAddress=0x83)
        self._cmd_serial = 0

    def initialize(self):
        try:
            cfg = self.dev.get_active_configuration()
            _log.debug("Configuration %s already set.", cfg.bConfigurationValue)
        except usb.core.USBError, e:
            _log.debug("Will configure device now.")
            self.dev.set_configuration()
            self.dev.set_interface_altsetting()

        try:
            usb.control.clear_feature(self.dev, usb.control.ENDPOINT_HALT, self.ep_in)
            usb.control.clear_feature(self.dev, usb.control.ENDPOINT_HALT, self.ep_out)
            usb.control.clear_feature(self.dev, usb.control.ENDPOINT_HALT, self.ep_int)
        except usb.core.USBError, e:
            _log.info("Clearing HALTs failed: %s", e)
            pass

        # do the init dance
        camstat = self._ctrl_read_assert(0x55, 1).tostring()
        if camstat not in ('A', 'C'):
            raise G3Error('Some kind of init error, camstat: %s', camstat)

        msg = self._ctrl_read_assert(0x01, 0x58)
        if camstat == 'A':
            _log.debug("Camera was already active")
            self._ctrl_read_assert(0x04, 0x50)
            return camstat

        _log.debug("Camera woken up, initializing")
        msg[0:0x40] = array('B', [0 for _ in range(0x40)])
        msg[0] = 0x10
        msg[0x40:] = msg[-0x10:]
        self._ctrl_write_assert(0x11, msg)
        self.ep_in.read(0x44)

        read = 0
        while read < 0x10:
            read += len(self.ep_int.read(0x10, timeout=500))

        cnt = 0
        while True:
            try:
                self.identify_camera()
                return
            except (USBError, G3Error):
                cnt += 1
                if cnt >=4:
                    raise

        return camstat

    def identify_camera(self):
        data = self._canon_dialogue(commands.IDENTIFY_CAMERA)
        model = extract_string(data, 0x5c)
        owner = extract_string(data, 0x7c)
        version = '.'.join([str(x) for x in data[0x5b:0x58:-1]])
        return model, owner, version

    def rc_start(self):
        while True:
            read = self.ep_int.read(0x10)
            if not len(read):
                _log.debug("No more data on the INT endpoint")
                break
            _log.debug("Got %s bytes from INT endpoint", len(read))

        old_timeout, self.dev.default_timeout = self.dev.default_timeout, 10000
        data = self._canon_dialogue_rc(commands.RC_INIT)
        self.dev.default_timeout = old_timeout
        return data

    def rc_stop(self):
        old_timeout, self.dev.default_timeout = self.dev.default_timeout, 10000
        data = self._canon_dialogue_rc(commands.RC_EXIT)
        self.dev.default_timeout = old_timeout
        return data

    def _ctrl_read(self, value, data_length=0, timeout=None):
        bRequest = 0x04 if data_length > 1 else 0x0c
        return self.dev.ctrl_transfer(0xc0, bRequest, wValue=value, wIndex=0,
                                      data_or_wLength=data_length,
                                      timeout=timeout)

    def _ctrl_read_assert(self,value, data_length=0, timeout=None):
        response = self._ctrl_read(value, data_length, timeout)
        if len(response) != data_length:
            raise G3Error("incorrect response length form camera")
        return response

    def _ctrl_write(self, value, data='', timeout=None):
        bRequest = 0x04 if len(data) > 1 else 0x0c
        return self.dev.ctrl_transfer(0x40, bRequest, wValue=value, wIndex=0,
                                      data_or_wLength=data,
                                      timeout=timeout)

    def _ctrl_write_assert(self, value, data='', timeout=None):
        i = self._ctrl_write(value, data, timeout)
        if i != len(data):
            raise G3Error("control write incomplete")
        return i

    def _canon_dialogue(self, cmd, payload=None):
        _log.debug("Executing command %s, expecting %s bytes back",
                   cmd['c_idx'], cmd['return_length'])

        packet = array('B', [0]*0x50)
        payload_length = len(payload) if payload else 0
        # request size
        packet[0:4] = array('B', struct.pack('<I', payload_length + 0x10))
        packet[0x40] = 2
        packet[0x44] = cmd['cmd1'];
        packet[0x47] = cmd['cmd2'];
        packet[4:8] = array('B', struct.pack('<I', cmd['cmd3']))
        packet[0x4c:0x4c+4] = array('B', struct.pack('<I', self._cmd_serial))
        self._cmd_serial += 1
        packet[0x48:0x48+4] = packet[0:4]

        if payload_length:
            packet.extend(array('B', payload))

        self._ctrl_write_assert(0x10, packet)

        # read the response
        total_read = int(cmd['return_length'])
        remainder_read = total_read % 0x40
        first_read = total_read - remainder_read

        data = self.ep_in.read(first_read)
        if not len(data) == first_read:
            raise G3Error("unexpected data length")

        if cmd['cmd3'] == 0x202:
            # variable-length response, read the lenght and
            # read the rest of the response nicely chunked
            resp_len = struct.unpack('<I', data[6:10].tostring())
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
            data.extend(self.ep_in.read(remainder_read))

        if len(data) != cmd['return_length']:
            raise G3Error("didn't get expected number of bytes in response")

#        if len(data) >= 0x50:
#            reported_len = struct.unpack('<I', data[0x48:0x48+4].tostring())
#            if reported_len != len(data):
#                import warnings; warnings.warn()

        return data

    def _canon_dialogue_rc(self, rc_cmd, arguments=None):
        old_timeout, self.dev.default_timeout = self.dev.default_timeout, 15000
        cmd = commands.CONTROL_CAMERA.copy()
        cmd['return_length'] += rc_cmd['return_length']
        payload = array('B', struct.pack('<I', rc_cmd['value']))
        if arguments is None:
            payload.fromstring('\x00\x00\x00\x00')
        else:
            payload.extend(arguments)
        try:
            return self._canon_dialogue(cmd, payload)
        finally:
            self.dev.default_timeout = old_timeout













