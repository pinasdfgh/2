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
from canon import CanonError

"""
USB Command structures extracted from gphoto2, see
    libgphoto2/camlibs/canon/usb.c for command structures;
    the containing directory for usage thereof.

TODO: Pythonify this code: commands should be objects with the
      basic pack/unpack logic return length calculation and such
      built in.
"""

import logging
from array import array

from canon.util import itole32a, le32toi, extract_string, le16toi

_log = logging.getLogger(__name__)

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

    @staticmethod
    def from_command_packet(data):
        """Return a command instance from a command packet.

        This is used for parsing sniffed USB traffic.

        """
        raise NotImplementedError()

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


class IdentifyCameraCmd(FixedResponseCommand):
    """Identify camera.

    ``execute()`` -> `(model, owner, version)` strings

    """
    cmd1 = 0x01
    cmd2 = 0x12
    resplen = 0x5c
    def _parse_response(self, data):
        model = extract_string(data, 0x1c)
        owner = extract_string(data, 0x3c)
        version = '.'.join([str(x) for x in data[0x1b:0x17:-1]])
        return model, owner, version

class IdentifyFlashDeviceCmd(VariableResponseCommand):
    """Flash device identification.
    """

    cmd1 = 0x0a
    cmd2 = 0x11
    def _parse_response(self, data):
        return extract_string(data)

class GenericLockKeysCmd(FixedResponseCommand):
    """Lock keys and turn off LCD
    """
    cmd1 = 0x20
    cmd2 = 0x12
    resplen = 0x14

class SetOwnerCmd(FixedResponseCommand):
    """Change camera owner
    """
    cmd1 = 0x05
    cmd2 = 0x12
    resplen = 0x14
    def __init__(self, owner):
        payload = array('B', owner + '\x00')
        super(SetOwnerCmd, self).__init__(payload)

class GetOwnerCmd(FixedResponseCommand):
    """Doesn't appear to be supported by the G3.
    """
    cmd1 = 0x05
    cmd2 = 0x12
    resplen = 0x34

class GetTimeCmd(FixedResponseCommand):
    cmd1 = 0x03
    cmd2 = 0x12
    resplen = 0x20
    def _parse_response(self, data):
        return le32toi(data, 0x14)

class SetTimeCmd(FixedResponseCommand):
    cmd1 = 0x04
    cmd2 = 0x12
    resplen = 0x14
    def __init__(self, new_timestamp):
        payload = itole32a(new_timestamp) + array('B', [0] * 8)
        super(SetTimeCmd, self).__init__(payload)

class GetPowerStatusCmd(FixedResponseCommand):
    cmd1 = 0x0a
    cmd2 = 0x12
    resplen = 0x18

class CheckACPowerCmd(GetPowerStatusCmd):
    def _parse_response(self, data):
        return bool((data[0x17] & 0x20) == 0x00)

class GetPicAbilitiesCmd(FixedResponseCommand):
    cmd1 = 0x1f
    cmd2 = 0x12
    resplen = 0x354
    def _parse_response(self, data):
        struct_size = le16toi(data, 0x14)
        model_id = le32toi(data[0x16:0x1a])
        camera_name = extract_string(data, 0x1a)
        num_entries = le32toi(data, 0x3a)
        _log.info("abilities of {} (0x{:x}): 0x{:x} long, n={}"
                 .format(camera_name, model_id, struct_size, num_entries))
        offset = 0x3e
        abilities = []
        for i in xrange(num_entries):
            name = extract_string(data, offset)
            height = le32toi(data, offset + 20)
            width = le32toi(data, offset + 24)
            idx = le32toi(data, offset + 28)
            _log.info(" {:-3} - 0x{:04x} {:20} {}x{}"
                      .format(i, idx, name, width, height))
            offset += 32
            abilities.append((idx, name, height, width))

        return abilities

# Regular camera and storage commands

GET_FILE = {
    'c_idx': 'GET_FILE',
    'description': "Get file",
    'cmd1': 0x01,
    'cmd2': 0x11,
    'cmd3': 0x202,
    'return_length': 0x40 }

MKDIR = {
    'c_idx': 'MKDIR',
    'description': "Make directory",
    'cmd1': 0x05,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x54 }

RMDIR = {
    'c_idx': 'RMDIR',
    'description': "Remove directory",
    'cmd1': 0x06,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x54 }

DISK_INFO = {
    'c_idx': 'DISK_INFO',
    'description': "Disk info request",
    'cmd1': 0x09,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x5c }

FLASH_DEVICE_IDENT = {
    'c_idx': 'FLASH_DEVICE_IDENT',
    'description': "Flash device ident",
    'cmd1': 0x0a,
    'cmd2': 0x11,
    'cmd3': 0x202,
    'return_length': 0x40 }

DELETE_FILE_2 = {
    'c_idx': 'DELETE_FILE_2',
    'description': "Delete file",
    'cmd1': 0x0a,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x54 }

GET_DIR = {
    'c_idx': 'GET_DIR',
    'description': "Get directory entries",
    'cmd1': 0x0b,
    'cmd2': 0x11,
    'cmd3': 0x202,
    'return_length': 0x40 }

DELETE_FILE = {
    'c_idx': 'DELETE_FILE',
    'description': "Delete file",
    'cmd1': 0x0d,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x54 }

DISK_INFO_2 = {
    'c_idx': 'DISK_INFO_2',
    'description': "Disk info request (new)",
    'cmd1': 0x0d,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x5c }

SET_ATTR = {
    'c_idx': 'SET_ATTR',
    'description': "Set file attributes",
    'cmd1': 0x0e,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x54 }

FLASH_DEVICE_IDENT_2 = {
    'c_idx': 'FLASH_DEVICE_IDENT_2',
    'description': "Flash device ident (new)",
    'cmd1': 0x0e,
    'cmd2': 0x11,
    'cmd3': 0x202,
    'return_length': 0x40 }

SET_FILE_TIME = {
    'c_idx': 'SET_FILE_TIME',
    'description': "Set file time",
    'cmd1': 0x0f,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x54 }

IDENTIFY_CAMERA = {
    'c_idx': 'IDENTIFY_CAMERA',
    'description': "Identify camera",
    'cmd1': 0x01,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x9c }

GET_TIME = {
    'c_idx': 'GET_TIME',
    'description': "Get time",
    'cmd1': 0x03,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x60 }

SET_TIME = {
    'c_idx': 'SET_TIME',
    'description': "Set time",
    'cmd1': 0x04,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x54 }

CAMERA_CHOWN = {
    'c_idx': 'CAMERA_CHOWN',
    'description': "Change camera owner",
    'cmd1': 0x05,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x54 }

GET_OWNER = {
    'c_idx': 'GET_OWNER',
    'description': "Get owner name (new)",
    'cmd1': 0x05,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x74 }

CAMERA_CHOWN_2 = {
    'c_idx': 'CAMERA_CHOWN_2',
    'description': "Change owner (new)",
    'cmd1': 0x06,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x54 }

POWER_STATUS = {
    'c_idx': 'POWER_STATUS',
    'description': "Power supply status",
    'cmd1': 0x0a,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x58 }

CONTROL_CAMERA = {
    'c_idx': 'RC_CAMERA',
    'description': "Remote camera control",
    'cmd1': 0x13,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x40 }

POWER_STATUS_2 = {
    'c_idx': 'POWER_STATUS_2',
    'description': "Power supply status (new)",
    'cmd1': 0x13,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x58 }

RETRIEVE_CAPTURE = {
    'c_idx': 'RETRIEVE_CAPTURE',
    'description': "Download a captured image",
    'cmd1': 0x17,
    'cmd2': 0x12,
    'cmd3': 0x202,
    'return_length': 0x40 }

RETRIEVE_PREVIEW = {
    'c_idx': 'RETRIEVE_PREVIEW',
    'description': "Download a captured preview",
    'cmd1': 0x18,
    'cmd2': 0x12,
    'cmd3': 0x202,
    'return_length': 0x40 }

UNKNOWN_FUNCTION = {
    'c_idx': 'UNKNOWN_FUNCTION',
    'description': "Unknown function",
    'cmd1': 0x1a,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x80 }

EOS_LOCK_KEYS = {
    'c_idx': 'EOS_LOCK_KEYS',
    'description': "EOS lock keys",
    'cmd1': 0x1b,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x54 }

EOS_UNLOCK_KEYS = {
    'c_idx': 'EOS_UNLOCK_KEYS',
    'description': "EOS unlock keys",
    'cmd1': 0x1c,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x54 }

EOS_GET_BODY_ID = {
    'c_idx': 'EOS_GET_BODY_ID',
    'description': "EOS get body ID",
    'cmd1': 0x1d,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x58 }

GET_PIC_ABILITIES = {
    'c_idx': 'GET_PIC_ABILITIES',
    'description': "Get picture abilities",
    'cmd1': 0x1f,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x394 }

GENERIC_LOCK_KEYS = {
    'c_idx': 'GENERIC_LOCK_KEYS',
    'description': "Lock keys and turn off LCD",
    'cmd1': 0x20,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x54 }

#20D_UNKNOWN_1 = {
#    'c_idx': '20D_UNKNOWN_1',
#    'description': "Unknown EOS 20D function",
#    'cmd1': 0x21,
#    'cmd2': 0x12,
#    'cmd3': 0x201,
#    'return_length': 0x54 }
#
#20D_UNKNOWN_2 = {
#    'c_idx': '20D_UNKNOWN_2',
#    'description': "Unknown EOS 20D function",
#    'cmd1': 0x22,
#    'cmd2': 0x12,
#    'cmd3': 0x201,
#    'return_length': 0x54 }

EOS_GET_BODY_ID_2 = {
    'c_idx': 'EOS_GET_BODY_ID_2',
    'description': "Get body ID (new)",
    'cmd1': 0x23,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x58 }

GET_PIC_ABILITIES_2 = {
    'c_idx': 'GET_PIC_ABILITIES_2',
    'description': "Get picture abilities (new)",
    'cmd1': 0x24,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x474 }

CONTROL_CAMERA_2 = {
    'c_idx': 'RC_CAMERA_2',
    'description': "Remote camera control (new)",
    'cmd1': 0x25,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x40 }

RETRIEVE_CAPTURE_2 = {
    'c_idx': 'RETRIEVE_CAPTURE_2',
    'description': "Download captured image (new)",
    'cmd1': 0x26,
    'cmd2': 0x12,
    'cmd3': 0x202,
    'return_length': 0x40 }

LOCK_KEYS_2 = {
    'c_idx': 'LOCK_KEYS_2',
    'description': "Lock keys (new)",
    'cmd1': 0x35,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x5c }

UNLOCK_KEYS_2 = {
    'c_idx': 'UNLOCK_KEYS_2',
    'description': "Unlock keys (new)",
    'cmd1': 0x36,
    'cmd2': 0x12,
    'cmd3': 0x201,
    'return_length': 0x54 }

SET_ATTR_2 = {
    'c_idx': 'SET_ATTR_2',
    'description': "Set file attributes (new))",
    'cmd1': 0x07,
    'cmd2': 0x11,
    'cmd3': 0x201,
    'return_length': 0x54 }

def lookup(cmd1, cmd2, cmd3):
    for name, c in globals().iteritems():
        if not name.isupper() or type(c) != dict:
            continue
        if not all(((k in c) for k in ('cmd1', 'cmd2', 'cmd3'))):
            continue
        if c['cmd1'] == cmd1 and c['cmd2'] == cmd2 and c['cmd3'] == cmd3:
            return c['c_idx']

# Remote control sub-commands

RC_INIT = {
    'c_idx': 'RC_INIT',
    'description': "Camera control init",
    'value': 0x00,
    'cmd_len': 0x18,
    'return_length': 0x1c }

RC_SHUTTER_RELEASE = {
    'c_idx': 'RC_SHUTTER_RELEASE',
    'description': "Release shutter",
    'value': 0x04,
    'cmd_len': 0x18,
    'return_length': 0x1c }

RC_SET_PARAMS = {
    'c_idx': 'RC_SET_PARAMS',
    'description': "Set release params",
    'value': 0x07,
    'cmd_len': 0x3c,
    'return_length': 0x1c }

RC_SET_TRANSFER_MODE = {
    'c_idx': 'RC_SET_TRANSFER_MODE',
    'description': "Set transfer mode",
    'value': 0x09,
    'cmd_len': 0x1c,
    'return_length': 0x1c }

RC_GET_PARAMS = {
    'c_idx': 'RC_GET_PARAMS',
    'description': "Get release params",
    'value': 0x0a,
    'cmd_len': 0x18,
    'return_length': 0x4c }

RC_GET_ZOOM_POS = {
    'c_idx': 'RC_GET_ZOOM_POS',
    'description': "Get zoom position",
    'value': 0x0b,
    'cmd_len': 0x18,
    'return_length': 0x20 }

RC_SET_ZOOM_POS = {
    'c_idx': 'RC_SET_ZOOM_POS',
    'description': "Set zoom position",
    'value': 0x0c,
    'cmd_len': 0x1c,
    'return_length': 0x1c }

RC_GET_AVAILABLE_SHOT = {
    'c_idx': 'RC_GET_AVAILABLE_SHOT',
    'description': "Get available shot",
    'value': 0x0d,
    'cmd_len': 0x18,
    'return_length': 0x20 }

RC_GET_CUSTOM_FUNC = {
    'c_idx': 'RC_GET_CUSTOM_FUNC',
    'description': "Get custom func.",
    'value': 0x0f,
    'cmd_len': 0x22,
    'return_length': 0x26 }

RC_GET_EXT_PARAMS_SIZE = {
    'c_idx': 'RC_GET_EXT_PARAMS_SIZE',
    'description': "Get ext. release params size",
    'value': 0x10,
    'cmd_len': 0x1c,
    'return_length': 0x20 }

RC_GET_EXT_PARAMS = {
    'c_idx': 'RC_GET_EXT_PARAMS',
    'description': "Get ext. release params",
    'value': 0x12,
    'cmd_len': 0x1c,
    'return_length': 0x2c }

RC_SET_EXT_PARAMS = {
    'c_idx': 'RC_SET_EXT_PARAMS',
    'description': "Set extended params",
    'value': 0x13,
    'cmd_len': 0x15,
    'return_length': 0x1c }

RC_EXIT = {
    'c_idx': 'RC_EXIT',
    'description': "Exit release control",
    'value': 0x01,
    'cmd_len': 0x18,
    'return_length': 0x1c }

RC_UNKNOWN_1 = {
    'c_idx': 'RC_UNKNOWN_1',
    'description': "Unknown remote subcode",
    'value': 0x1b,
    'cmd_len': 0x08,
    'return_length': 0x5e }

RC_UNKNOWN_2 = {
    'c_idx': 'RC_UNKNOWN_2',
    'description': "Unknown remote subcode",
    'value': 0x1c,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_VIEWFINDER_START = {
    'c_idx': 'RC_VIEWFINDER_START',
    'description': "Start viewfinder",
    'value': 0x02,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_VIEWFINDER_STOP = {
    'c_idx': 'RC_VIEWFINDER_STOP',
    'description': "Stop viewfinder",
    'value': 0x03,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_SET_CUSTOM_FUNC = {
    'c_idx': 'RC_SET_CUSTOM_FUNC',
    'description': "Set custom func.",
    'value': 0x0e,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_GET_EXT_PARAMS_VER = {
    'c_idx': 'RC_GET_EXT_PARAMS_VER',
    'description': "Get extended params version",
    'value': 0x11,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_SELECT_CAM_OUTPUT = {
    'c_idx': 'RC_SELECT_CAM_OUTPUT',
    'description': "Select camera output",
    'value': 0x14,
    'cmd_len': 0x00,
    'return_length': 0x00 }

def lookup_rc(subcmd):
    for name, c in globals().iteritems():
        if (not name.isupper() or not name.startswith('RC_')
                or type(c) != dict):
            continue
        if not all(((k in c) for k in ('c_idx', 'value', 'cmd_len'))):
            continue
        if c['value'] == subcmd:
            return c['c_idx']

if __name__ == '__main__':
    print COMMANDS
