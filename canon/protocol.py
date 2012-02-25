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

from canon import CanonError
from canon.util import le32toi, hexdump, itole32a

_log = logging.getLogger(__name__)

MAX_CHUNK_SIZE = 0x1400

COMMANDS = []

class CommandMeta(type):
    def __new__(cls, name, bases, attrs):
        super_new = super(CommandMeta, cls).__new__
        parents = [b for b in bases if isinstance(b, CommandMeta)]
        if not parents:
            return super_new(cls, name, bases, attrs)

        new_class = super_new(cls, name, bases, attrs)
        if new_class.is_complete_command():
            COMMANDS.append(new_class)
        return new_class

class Command(object):
    """A USB camera command.

    Subclasses of :class:`Command` are concrete commands to be executed on the
    camera. Instances thereof can run themselves on a :class:`CanonUSB`
    instance and should each implement some sort of response parsing.

    cmd1, cmd2 and cmd3 define the command to be executed.

    All of the following properties need to be set for a command class:

    ``cmd1`` is a command code.

    ``cmd2`` is `0x11` for storage and `0x12` for control commands.

    ``cmd3`` is `0x201` for fixed-response-length commands and
    `0x202` for variable length.

    """
    __metaclass__ = CommandMeta

    cmd1 = None
    cmd2 = None
    cmd3 = None

    MAX_CHUNK_SIZE = 0x1400

    _cmd_serial = 0

    _required_props = ['cmd1', 'cmd2', 'cmd3']

    @classmethod
    def _next_serial(cls):
        cls._cmd_serial += ((cls._cmd_serial % 8)) or 5 # just playin'
        if cls._cmd_serial > 65530:
            cls._cmd_serial = 0
        return cls._cmd_serial | 0x12<<16

    @classmethod
    def is_complete_command(cls):
        for p in cls._required_props:
            if not hasattr(cls, p):
                return False
            if getattr(cls, p) is None:
                return False
        return True

    def __init__(self, payload=None, serial=None):
        if not self.is_complete_command():
            raise AssertionError('{} is incomplete?'.format(self))
        assert ((isinstance(payload, array) and payload.itemsize == 1)
                    or payload is None)

        self._serial = serial
        payload_length = len(payload) if payload else 0
        self._command_header = self._construct_command_header(payload_length)
        self._payload = payload
        self._response_header = None

    @property
    def command_header(self):
        return self._command_header

    @property
    def payload(self):
        return self._payload if self._payload else array('B')

    @property
    def response_header(self):
        return self._response_header

    @response_header.setter
    def response_header(self, data):
        """TODO: check for the same serial and stuff...
        """
        assert isinstance(data, array)
        assert data.itemsize == 1
        assert len(data) == 0x40
        self._response_header = data

    @property
    def response_status(self):
        raise NotImplementedError()

    @property
    def response_length(self):
        raise NotImplementedError()

    @property
    def serial(self):
        """Return the serial id of this command.

        Generate one if not given in the constructor.

        """
        if self._serial is None:
            self._serial = self._next_serial()
        return self._serial

    @property
    def name(self):
        """Simply the class name for convenient access.
        """
        return self.__class__.__name__

    @property
    def first_chunk_size(self):
        """Return the length of the first chunk of data to be read.

        This differs for different commands, but should always be
        at least 0x40.
        """
        raise NotImplementedError()

    @classmethod
    def from_command_packet(data):
        """Return a command instance from a command packet.

        This is used for parsing sniffed USB traffic.

        """
        if not isinstance(data, array):
            data = array('B', data)
        assert len(data) >= 0x40
        request_size = data[0:4]
        cmd1 = data[0x44]
        cmd2 = data[0x47]
        cmd3 = le32toi(data, 4)
        serial = data[0x4c:0x50]

#        cmd_class =
#        return CanonUSBCommand(cmd1, cmd2, cmd3, serial, data[0x50:])

    def _construct_command_header(self, payload_length):
        """Return the 0x50 bytes to send down the control pipe.

        The structure is described here
        http://www.graphics.cornell.edu/~westin/canon/ch03s02.html

        """
        request_size = itole32a(payload_length + 0x10)

        # we dump a 0x50 (80) byte command block
        # the first 0x40 of which are some kind of standard header
        # the next 0x10 seem to be the header for the next layer
        # but it's all the same for us
        packet = array('B', [0] * 0x50)

        # request size is the total transmitted size - the first 0x40 bytes
        packet[0:4] = request_size

        # 0x02 just works, gphoto2 does magic for other camera classes
        packet[0x40] = 0x02

        packet[0x44] = self.cmd1
        # must do this for newer cameras, just a note
        #packet[0x46] = 0x10 if self.cmd3 == 0x201 else 0x20
        packet[0x47] = self.cmd2
        packet[4:8] = itole32a(self.cmd3)
        packet[0x48:0x48+4] = request_size # yes, again

        # this must be matched in the response
        packet[0x4c:0x4c+4] = itole32a(self.serial)

        return packet

    @classmethod
    def next_chunk_size(cls, remaining):
        """Calculate the size of the next chunk to read.

        See
        http://www.graphics.cornell.edu/~westin/canon/ch03s02.html#par.VarXfers

        """
        if remaining > cls.MAX_CHUNK_SIZE:
            return cls.MAX_CHUNK_SIZE
        elif remaining > 0x40:
            return (remaining // 0x40) * 0x40
        else:
            return remaining

    @classmethod
    def chunk_sizes(cls, bytes_to_read):
        """Yield chunk sizes to read.
        """
        while bytes_to_read:
            chunk = cls.next_chunk_size(bytes_to_read)
            bytes_to_read -= chunk
            yield chunk

    def _send(self, usb):
        """Send a command for execution to the camera.

        This method sends the command header and payload down the control
        pipe, reads the response header and returns an iterator over the
        response payload.

        """
        _log.info("--> {0.name:s} (0x{0.cmd1:x}, 0x{0.cmd2:x}, "
                  "0x{0.cmd3:x}), #{1:0}"
                  .format(self, self.serial & 0x0000ffff))

        # control out, then bulk in the first chunk
        usb.control_write(0x10, self.command_header + self.payload)
        data = usb.bulk_read(self.first_chunk_size)

        # store the response header
        self.response_header = data[:0x40]

        # return an iterator over the response data
        return self._reader(usb, data[0x40:])

    def _reader(self, usb, first_chunk):
        raise NotImplementedError()

    def _parse_response(self, data):
        return data

    def execute(self, usb):
        reader = self._send(usb)
        data = array('B')
        for chunk in reader:
            data.extend(chunk)
        return self._parse_response(data)

    def __repr__(self):
        return '<{} 0x{:x} 0x{:x} 0x{:x} at 0x{:x}>'.format(
                    self.name, self.cmd1, self.cmd2, self.cmd3, hash(self))

class GenericCommand(Command):
    @classmethod
    def is_complete_command(cls):
        return True

    def __init__(self, cmd1, cmd2, cmd3, payload=None, serial=None):
        assert cmd1 and cmd2 and cmd3
        self.cmd1 = cmd1
        self.cmd2 = cmd2
        self.cmd3 = cmd3
        super(GenericCommand, self).__init__(payload, serial)


class VariableResponseCommand(Command):
    cmd3 = 0x202
    first_chunk_size = 0x40

    @property
    def response_length(self):
        """Return the response length, excluding the first 0x40 bytes.
        """
        if not self.response_header:
            raise CanonError("_send() this command first.")
        return le32toi(self.response_header, 6)

    def _reader(self, usb, first_chunk):
        _log.debug("variable response says 0x{:x} bytes follow"
                   .format(self.response_length))
        _log.info("<-- {0.name:s} #{1:0} retlen 0x{2:x} "
                  .format(self, self.serial & 0x0000ffff,
                          self.response_length + 0x40))

        # this is normally empty, but let's make sure
        if first_chunk:
            yield first_chunk

        remaining = self.response_length - len(first_chunk)
        for chunk_size in self.chunk_sizes(remaining):
            yield usb.bulk_read(chunk_size)

class FixedResponseCommand(Command):
    cmd3 = 0x201
    resplen = None # the total data length to read, excluding the first 0x40

    _required_props = Command._required_props + ['resplen']

    @property
    def response_length(self):
        """Extract resplen from the response header

        For cmd3=0x201 (fixed response length) commands word at 0x00 is
        response length excluding the first 0x40, as well as the word at
        0x48, the header of the next layer?

        """
        if not self.response_header:
            raise CanonError("_send() this command first.")
        return le32toi(self.response_header, 0)

    @property
    def first_chunk_size(self):
        return self.next_chunk_size(self.resplen + 0x40)

    def _correct_resplen(self, already_got=0):
        if self.response_length != self.resplen:
            _log.warn("BAD response length, correcting 0x{:x} to 0x{:x} "
                      .format(self.resplen, self.response_length))
        return self.response_length - already_got

    def _reader(self, usb, first_chunk):
        remaining = self._correct_resplen(len(first_chunk))

        if len(first_chunk) < 0x0c:
            # need another chunk to get to the response length
            chunk_len = self.next_chunk_size(remaining)
            first_chunk.extend(usb.bulk_read(chunk_len))
            remaining -= chunk_len

        assert len(first_chunk) >= 0x0c

        # word at 0x50 is status byte
        self.status = le32toi(first_chunk, 0x10)
        _log.info("<-- {0.name:s} #{1:0} status: 0x{2:x} "
                  .format(self, self.serial & 0x0000ffff,
                          self.status))

        yield first_chunk

        for chunk_size in self.chunk_sizes(remaining):
            yield usb.bulk_read(chunk_size)


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
            _log.warn("poller_ctx: -> entered while poller was active!")
            yield self._poller
            _log.warn("poller_ctx: <- pretending this isn't real")
        else:
            started = time.time()
            _log.info("poller_ctx: -> ({}, {})".format(size, timeout))
            self.start_poller(size, timeout)
            yield self._poller
            if self.is_polling:
                self.stop_poller()
            _log.info("poller_ctx: <- back in {:.3} ms"
                      .format((time.time() - started) * 1000))

    def control_read(self, wValue, data_length=0, timeout=None):
        """Read from the control pipe.

        ``bRequest`` is 0x4 if length of data is >1, 0x0c otherwise (length >1 ? 0x04 : 0x0C)
        ``bmRequestType`` is 0xC0 during read and 0x40 during write.

        """
        #
        bRequest = 0x04 if data_length > 1 else 0x0c
        _log.info("control_read (req: 0x{:x} wValue: 0x{:x}) reading 0x{:x} bytes"
                   .format(bRequest, wValue, data_length))

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

