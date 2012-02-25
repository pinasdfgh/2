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

from canon.protocol import FixedResponseCommand, VariableResponseCommand
from canon.util import itole32a, le32toi, extract_string, le16toi

_log = logging.getLogger(__name__)

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
    """Lock keys and turn off LCD.
    """
    cmd1 = 0x20
    cmd2 = 0x12
    resplen = 0x14

class SetOwnerCmd(FixedResponseCommand):
    """Change camera owner.
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
