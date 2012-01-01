import sys
import os
import logging
from array import array

import usb.core
import usb.util
import usb.control

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)
_log.addHandler(logging.StreamHandler())
logging.getLogger('usb').addHandler(logging.StreamHandler())

class G3Error(Exception): pass

class CommandMeta(type):
    pass

class Command(object):
    __metaclass__ = CommandMeta

class IdentifyCamera(Command):
    request_type = 0x01
    response_length = 0x9c

class RemoteControl(object):
    def __init__(self, camera):
        self.camera = camera

class Camera(object):

    VENDORID = 0x04a9
    PRODUCTID = 0x306e

    @classmethod
    def find(cls):
        dev = usb.core.find(idVendor=cls.VENDORID, idProduct=cls.PRODUCTID)
        if not dev:
            return None
        return cls(dev)

    def __init__(self, dev):
        self.dev = dev
        self.iface = iface = dev[0][0,0]
        self.ep_in = usb.util.find_descriptor(iface, bEndpointAddress=0x81)
        self.ep_out = usb.util.find_descriptor(iface, bEndpointAddress=0x02)
        self.ep_int = usb.util.find_descriptor(iface, bEndpointAddress=0x83)

    def initialize(self):
        # TODO: check readiness? status?

        # halt endpoints
#        usb.control.set_feature(self.dev, usb.control.ENDPOINT_HALT, self.ep_in)
#        usb.control.set_feature(self.dev, usb.control.ENDPOINT_HALT, self.ep_out)
#        usb.control.set_feature(self.dev, usb.control.ENDPOINT_HALT, self.ep_int)

        # do the init dance
        camstat = self._ctrl_read_assert(0x55, 1).tostring()
        if camstat not in ('A', 'C'):
            raise G3Error('Some kind of init error, camstat: %s', camstat)

        msg = self._ctrl_read_assert(0x01, 0x58)
        if camstat == 'A':
            self._ctrl_read_assert(0x04, 0x50)
            return camstat

        msg[0:0x40] = array('B', [0 for _ in range(0x40)])
        msg[0] = 0x10
        msg[0x40:] = msg[-0x10:]
        self._ctrl_write_assert(0x11, msg)
        self.ep_in.read(0x44)

        read = 0
        while read < 0x10:
            read += len(self.ep_int.read(0x10, timeout=500))

        return camstat

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


    def _status(self):
        """Identify camera" seems to be a command compatible with all
        * cameras, and one that doesn't change the camera state."""
        pass