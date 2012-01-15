# coding: utf-8
"""
USB Command structures extracted from gphoto2, see
    libgphoto2/camlibs/canon/usb.c for command structures
    the containing directory for usage thereof

TODO: Pythonify this code: commands should be objects with the
      basic pack/unpack logic return length calculation and such
      built in.
"""
from canon.util import Bitfield, Flag, BooleanFlag
import itertools

_codes = {}

class _code(object):
    _by_code = {}
    def __init__(self, code, description):
        global _codes
        _codes[code] = self
        self.code = code
        self.description = description
    def __repr__(self):
        return '0x%08x "%s"' % (self.code, self.description)

class status(object):
    OK = _code(0x00000000, 'Success.')
    NOT_FOUND = _code(0x02000022, 'File not found.')
    FILE_PROTECTED = _code(0x02000029, "File was protected")
    FS_FULL = _code(0x0200002a, "Compact Flash card full (on set transfer mode and release shutter)")
    LOCK_KEYS_FAILED = _code(0x02000081, "EOS lock keys failed, e.g. shutter release is half-depressed or camera is in review or menu mode.")
    UNLOCK_KEYS_FAILED = _code(0x02000082, "EOS unlock keys failed, e.g. tried to unlock keys when they weren't locked to begin with.")
    RC_INIT_FAILED = _code(0x02000085, "camera control initialization failed. Couldn't extend lens (on G2) Camera was left in camera control modeFor D60: we just filled the CF card (on next camera control initialization; power cycle clears this)")
    BAD_REQUEST = _code(0x02000086, "Path not found or invalid parameters. Indicates either that the pathname wasn't found, e.g. for Get Directory, or that the command block was in error, e.g. the length wasn't correct, or the command for Set File Attributes had only one string, rather than a pathname followed by a filename.")
    NEW_SHIT = _code(0x00000086, "Returned by camera in newer protocol (e.g. EOS 20D) from Unlock keys when keys weren't locked.")
    NO_FLASH = _code(0x02000087, "No Compact Flash card")

    @classmethod
    def lookup(cls, code):
        global _codes
        return _codes.get(code)

class Command(object):
    def run(self, usb):
        # construct payload
        # send, receive
        # parse, return
        pass

class StorageCommand(Command):
    cmd2 = 0x11

class ControlCommand(Command):
    cmd2 = 0x12

class RemoteControlSubcommand(ControlCommand):
    cmd1 = 0x13

class LongCommandMixin(object):
    cmd3 = 0x202
    retlen = 0x40

class FixedCommandMixin(object):
    cmd3 = 0x201

class GetFileCmd(StorageCommand, LongCommandMixin):
    cmd1 = 0x01
    description = "Get file"

class MakeDirectoryCmd(StorageCommand, FixedCommandMixin):
    description = "Make directory"
    cmd1 = 0x05
    retlen = 0x54

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
    'c_idx': 'CONTROL_CAMERA',
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
    'c_idx': 'CONTROL_CAMERA_2',
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

ALL = [GET_FILE, MKDIR, RMDIR, DISK_INFO, FLASH_DEVICE_IDENT, DELETE_FILE_2,
       GET_DIR, DELETE_FILE, DISK_INFO_2, SET_ATTR, FLASH_DEVICE_IDENT_2,
       SET_FILE_TIME, IDENTIFY_CAMERA, GET_TIME, SET_TIME, CAMERA_CHOWN,
       GET_OWNER, CAMERA_CHOWN_2, POWER_STATUS, CONTROL_CAMERA,
       POWER_STATUS_2, RETRIEVE_CAPTURE, RETRIEVE_PREVIEW, UNKNOWN_FUNCTION,
       EOS_LOCK_KEYS, EOS_UNLOCK_KEYS, EOS_GET_BODY_ID, GET_PIC_ABILITIES,
       GENERIC_LOCK_KEYS, EOS_GET_BODY_ID_2, GET_PIC_ABILITIES_2,
       CONTROL_CAMERA_2, RETRIEVE_CAPTURE_2, LOCK_KEYS_2, UNLOCK_KEYS_2,
       SET_ATTR_2]

RC_INIT = {
    'c_idx': 'CONTROL_INIT',
    'description': "Camera control init",
    'value': 0x00,
    'cmd_len': 0x18,
    'return_length': 0x1c }

RC_SHUTTER_RELEASE = {
    'c_idx': 'CONTROL_SHUTTER_RELEASE',
    'description': "Release shutter",
    'value': 0x04,
    'cmd_len': 0x18,
    'return_length': 0x1c }

RC_SET_PARAMS = {
    'c_idx': 'CONTROL_SET_PARAMS',
    'description': "Set release params",
    'value': 0x07,
    'cmd_len': 0x3c,
    'return_length': 0x1c }

RC_SET_TRANSFER_MODE = {
    'c_idx': 'CONTROL_SET_TRANSFER_MODE',
    'description': "Set transfer mode",
    'value': 0x09,
    'cmd_len': 0x1c,
    'return_length': 0x1c }

RC_GET_PARAMS = {
    'c_idx': 'CONTROL_GET_PARAMS',
    'description': "Get release params",
    'value': 0x0a,
    'cmd_len': 0x18,
    'return_length': 0x4c }

RC_GET_ZOOM_POS = {
    'c_idx': 'CONTROL_GET_ZOOM_POS',
    'description': "Get zoom position",
    'value': 0x0b,
    'cmd_len': 0x18,
    'return_length': 0x20 }

RC_SET_ZOOM_POS = {
    'c_idx': 'CONTROL_SET_ZOOM_POS',
    'description': "Set zoom position",
    'value': 0x0c,
    'cmd_len': 0x1c,
    'return_length': 0x1c }

RC_GET_AVAILABLE_SHOT = {
    'c_idx': 'CONTROL_GET_AVAILABLE_SHOT',
    'description': "Get available shot",
    'value': 0x0d,
    'cmd_len': 0x18,
    'return_length': 0x20 }

RC_GET_CUSTOM_FUNC = {
    'c_idx': 'CONTROL_GET_CUSTOM_FUNC',
    'description': "Get custom func.",
    'value': 0x0f,
    'cmd_len': 0x22,
    'return_length': 0x26 }

RC_GET_EXT_PARAMS_SIZE = {
    'c_idx': 'CONTROL_GET_EXT_PARAMS_SIZE',
    'description': "Get ext. release params size",
    'value': 0x10,
    'cmd_len': 0x1c,
    'return_length': 0x20 }

RC_GET_EXT_PARAMS = {
    'c_idx': 'CONTROL_GET_EXT_PARAMS',
    'description': "Get ext. release params",
    'value': 0x12,
    'cmd_len': 0x1c,
    'return_length': 0x2c }

RC_SET_EXT_PARAMS = {
    'c_idx': 'CONTROL_SET_EXT_PARAMS',
    'description': "Set extended params",
    'value': 0x13,
    'cmd_len': 0x15,
    'return_length': 0x1c }

RC_EXIT = {
    'c_idx': 'CONTROL_EXIT',
    'description': "Exit release control",
    'value': 0x01,
    'cmd_len': 0x18,
    'return_length': 0x1c }

RC_UNKNOWN_1 = {
    'c_idx': 'CONTROL_UNKNOWN_1',
    'description': "Unknown remote subcode",
    'value': 0x1b,
    'cmd_len': 0x08,
    'return_length': 0x5e }

RC_UNKNOWN_2 = {
    'c_idx': 'CONTROL_UNKNOWN_2',
    'description': "Unknown remote subcode",
    'value': 0x1c,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_VIEWFINDER_START = {
    'c_idx': 'CONTROL_VIEWFINDER_START',
    'description': "Start viewfinder",
    'value': 0x02,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_VIEWFINDER_STOP = {
    'c_idx': 'CONTROL_VIEWFINDER_STOP',
    'description': "Stop viewfinder",
    'value': 0x03,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_SET_CUSTOM_FUNC = {
    'c_idx': 'CONTROL_SET_CUSTOM_FUNC',
    'description': "Set custom func.",
    'value': 0x0e,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_GET_EXT_PARAMS_VER = {
    'c_idx': 'CONTROL_GET_EXT_PARAMS_VER',
    'description': "Get extended params version",
    'value': 0x11,
    'cmd_len': 0x00,
    'return_length': 0x00 }

RC_SELECT_CAM_OUTPUT = {
    'c_idx': 'CONTROL_SELECT_CAM_OUTPUT',
    'description': "Select camera output",
    'value': 0x14,
    'cmd_len': 0x00,
    'return_length': 0x00 }

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

class ReleaseParams(Bitfield):
    APERTURE_F1_2 = 0x0d
    APERTURE_F1_4 = 0x10
    APERTURE_F1_6 = 0x13
    APERTURE_F1_8 = 0x15
    APERTURE_F2_0 = 0x18
    APERTURE_F2_2 = 0x1b
    APERTURE_F2_5 = 0x1d
    APERTURE_F2_8 = 0x20
    APERTURE_F3_2 = 0x23
    APERTURE_F3_5 = 0x25
    APERTURE_F4_0 = 0x28
    APERTURE_F4_5 = 0x2b
    APERTURE_F5_0 = 0x2d
    APERTURE_F5_6 = 0x30
    APERTURE_F6_3 = 0x33
    APERTURE_F7_1 = 0x35
    APERTURE_F8 = 0x38
    APERTURE_F9 = 0x3b
    APERTURE_F10 = 0x3d
    APERTURE_F11 = 0x40
    APERTURE_F13 = 0x43
    APERTURE_F14 = 0x45
    APERTURE_F16 = 0x48
    APERTURE_F18 = 0x4b
    APERTURE_F20 = 0x4d
    APERTURE_F22 = 0x50
    APERTURE_F25 = 0x53
    APERTURE_F29 = 0x55
    APERTURE_F32 = 0x58

    SHUTTER_SPEED_BULB = 0x04
    SHUTTER_SPEED_30_SEC = 0x10
    SHUTTER_SPEED_25_SEC = 0x13
    SHUTTER_SPEED_20_SEC = 0x15
    SHUTTER_SPEED_15_SEC = 0x18
    SHUTTER_SPEED_13_SEC = 0x1b
    SHUTTER_SPEED_10_SEC = 0x1d
    SHUTTER_SPEED_8_SEC = 0x20
    SHUTTER_SPEED_6_SEC = 0x23
    SHUTTER_SPEED_5_SEC = 0x25
    SHUTTER_SPEED_4_SEC = 0x28
    SHUTTER_SPEED_3_2_SEC = 0x2b
    SHUTTER_SPEED_2_5_SEC = 0x2d
    SHUTTER_SPEED_2_SEC = 0x30
    SHUTTER_SPEED_1_6_SEC = 0x32
    SHUTTER_SPEED_1_3_SEC = 0x35
    SHUTTER_SPEED_1_SEC = 0x38
    SHUTTER_SPEED_0_8_SEC = 0x3b
    SHUTTER_SPEED_0_6_SEC = 0x3d
    SHUTTER_SPEED_0_5_SEC = 0x40
    SHUTTER_SPEED_0_4_SEC = 0x43
    SHUTTER_SPEED_0_3_SEC = 0x45
    SHUTTER_SPEED_1_4 = 0x48
    SHUTTER_SPEED_1_5 = 0x4b
    SHUTTER_SPEED_1_6 = 0x4d
    SHUTTER_SPEED_1_8 = 0x50
    SHUTTER_SPEED_1_10 = 0x53
    SHUTTER_SPEED_1_13 = 0x55
    SHUTTER_SPEED_1_15 = 0x58
    SHUTTER_SPEED_1_20 = 0x5b
    SHUTTER_SPEED_1_25 = 0x5d
    SHUTTER_SPEED_1_30 = 0x60
    SHUTTER_SPEED_1_40 = 0x63
    SHUTTER_SPEED_1_50 = 0x65
    SHUTTER_SPEED_1_60 = 0x68
    SHUTTER_SPEED_1_80 = 0x6b
    SHUTTER_SPEED_1_100 = 0x6d
    SHUTTER_SPEED_1_125 = 0x70
    SHUTTER_SPEED_1_160 = 0x73
    SHUTTER_SPEED_1_200 = 0x75
    SHUTTER_SPEED_1_250 = 0x78
    SHUTTER_SPEED_1_320 = 0x7b
    SHUTTER_SPEED_1_400 = 0x7d
    SHUTTER_SPEED_1_500 = 0x80
    SHUTTER_SPEED_1_640 = 0x83
    SHUTTER_SPEED_1_800 = 0x85
    SHUTTER_SPEED_1_1000 = 0x88
    SHUTTER_SPEED_1_1250 = 0x8b
    SHUTTER_SPEED_1_1600 = 0x8d
    SHUTTER_SPEED_1_2000 = 0x90
    SHUTTER_SPEED_1_2500 = 0x93
    SHUTTER_SPEED_1_3200 = 0x95
    SHUTTER_SPEED_1_4000 = 0x98
    SHUTTER_SPEED_1_5000 = 0x9a
    SHUTTER_SPEED_1_6400 = 0x9d
    SHUTTER_SPEED_1_8000 = 0xA0

    ISO_50 = 0x40
    ISO_100 = 0x48
    ISO_125 = 0x4b
    ISO_160 = 0x4d
    ISO_200 = 0x50
    ISO_250 = 0x53
    ISO_320 = 0x55
    ISO_400 = 0x58
    ISO_500 = 0x5b
    ISO_640 = 0x5d
    ISO_800 = 0x60
    ISO_1000 = 0x63
    ISO_1250 = 0x65
    ISO_1600 = 0x68
    ISO_3200 = 0x70

    AUTO_FOCUS_ONE_SHOT = 0
    AUTO_FOCUS_AI_SERVO = 1
    AUTO_FOCUS_AI_FOCUS = 2
    MANUAL_FOCUS = 3

    FLASH_MODE_OFF = 0
    FLASH_MODE_ON = 1
    FLASH_MODE_AUTO = 2

    BEEP_OFF = 0x00
    BEEP_ON = 0x01

    EXPOSURE_PLUS_2 = 0x10
    EXPOSURE_PLUS_1_ = 0x0d
    EXPOSURE_PLUS_1_1_2 = 0x0c
    EXPOSURE_PLUS_1_1_3 = 0x0b
    EXPOSURE_PLUS_1 = 0x08
    EXPOSURE_PLUS_0_2_3 = 0x05
    EXPOSURE_PLUS_0_1_2 = 0x04
    EXPOSURE_PLUS_0_1_3 = 0x03
    EXPOSURE_ZERO = 0x00
    EXPOSURE_MINUS_0_1_3 = 0xfd
    EXPOSURE_MINUS_0_1_2 = 0xfc
    EXPOSURE_MINUS_0_2_3 = 0xfb
    EXPOSURE_MINUS_1 = 0xf8
    EXPOSURE_MINUS_1_1_3 = 0xf5
    EXPOSURE_MINUS_1_1_2 = 0xf4
    EXPOSURE_MINUS_1_2_3 = 0xf3
    EXPOSURE_MINUS_2 = 0xf0

    IMAGE_FORMAT_RAW = (0x04, 0x02, 0x00)
    IMAGE_FORMAT_SMALL_NORMAL_JPEG = (0x02, 0x01, 0x02)
    IMAGE_FORMAT_SMALL_FINE_JPEG = (0x03, 0x01, 0x02)
    IMAGE_FORMAT_MEDIUM_NORMAL_JPEG = (0x02, 0x01, 0x01)
    IMAGE_FORMAT_MEDIUM_FINE_JPEG = (0x03, 0x01, 0x01)
    IMAGE_FORMAT_LARGE_NORMAL_JPEG = (0x02, 0x01, 0x00)
    IMAGE_FORMAT_LARGE_FINE_JPEG = (0x03, 0x01, 0x00)
    IMAGE_FORMAT_RAW_AND_SMALL_NORMAL_JPEG = (0x24, 0x12, 0x20)
    IMAGE_FORMAT_RAW_AND_SMALL_FINE_JPEG = (0x34, 0x12, 0x20)
    IMAGE_FORMAT_RAW_AND_MEDIUM_NORMAL_JPEG = (0x24, 0x12, 0x10)
    IMAGE_FORMAT_RAW_AND_MEDIUM_FINE_JPEG = (0x34, 0x12, 0x10)
    IMAGE_FORMAT_RAW_AND_LARGE_NORMAL_JPEG = (0x24, 0x12, 0x00)
    IMAGE_FORMAT_RAW_AND_LARGE_FINE_JPEG = (0x34, 0x12, 0x00)

    _size = 0x2f
    image_format = Flag(1, 3)
    flash = Flag(0x06, on=0x01, off=0x00)
    beep = Flag(0x07, on=0x01, off=0x00)
    focus_mode = Flag(0x12)
    iso = Flag(0x1a)
    aperture = Flag(0x1c)
    shutter_speed = Flag(0x1e)
    exposure_bias = Flag(0x20)
    shooting_mode = Flag(0x08)

