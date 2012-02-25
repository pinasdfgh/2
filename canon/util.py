#
# This file is part of canon-remote
# Copyright (C) 2011 Kiril Zyapkov
#
# canon-remote is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# canon-remote is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with canon-remote.  If not, see <http://www.gnu.org/licenses/>.
#

import struct
import string
from array import array
import math

ARRAY_FORMAT = [None, 'B', '<H', '<I', '<I', '<Q', '<Q', '<Q', '<Q']

def extract_string(data, start=0):
    try:
        end = data[start:].index(0x00)
    except (ValueError, IndexError):
        return None
    return data[start:start+end].tostring()

def le16toi(raw, start=None):
    raw = _normalize_to_string(raw)
    if start is not None:
        raw = raw[start:start+2]
    return struct.unpack('<H', raw)[0]

def le32toi(raw, start=None):
    raw = _normalize_to_string(raw)
    if start is not None:
        raw = raw[start:start+4]
    return struct.unpack('<I', raw)[0]

def itole32a(i):
    return array('B', struct.pack('<I', i))

def _normalize_to_string(raw):
    if isinstance(raw, array):
        raw = raw.tostring()
    elif type(raw) is str:
        pass
    elif type(raw) in (int, long):
        length = math.ceil(raw.bit_length() / 8.0)
        raw = array(ARRAY_FORMAT[length], [raw]).tostring()
    return raw

def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def hexdump(data, with_ascii=True, with_offset=True):
    """Return the binary data as nicely printed hexadecimal text.
    """
    if type(data) is str:
        data = array('B', data)
    elif type(data) is unicode:
        data = array('u', data)

    data = enumerate(chunks(data, 0x10)) # 16 bytes per line

    def format_row(idx, row):
        'line of text for the 16 bytes in row'
        line = ''
        if with_offset:
            line = '{:04x}  '.format(idx*0x10)

        halfs = []
        for half in chunks(row, 8): # split the 16 bytes in the middle
            half = ' '.join("{:02x}".format(x) for x in half)
            halfs.append(half)

        line += '  '.join(halfs)

        if not with_ascii:
            return line

        line = line.ljust(57) # adjust to 56 chars
        halfs = []
        for half in chunks(row, 8):
            chars = [(chr(c) if (chr(c) in string.ascii_letters
                                     or chr(c) in string.digits
                                     or chr(c) in string.punctuation
                                     or chr(c) == ' ')
                             else ('.' if c == 0x00 else ';'))
                     for c in half]
            half = ''.join(chars)
            halfs.append(half)
        line += ' '.join(halfs)
        return line

    out = [format_row(row_idx, row) for row_idx, row in data]

    return "\n".join(out)

