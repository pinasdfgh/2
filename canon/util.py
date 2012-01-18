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
import inspect
from orca.orca import isDiacriticalKey
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

class _BoundFlag(object):
    """An instance binging a ``Flag`` to a ``Bitfield``.
    """
    def __init__(self, bitfield, flag):
        self._bitfield = bitfield
        self._flag = flag
        for attr_name in ('_fmt', '_fmt_size', '_start', '_end', '_length',
                          'name'):
            setattr(self, attr_name, getattr(flag, attr_name))

    def set_(self, value):
        """Store integer value in this bitfield.
        """
        bytes_ = self._pack(value)
        self._store(bytes_)

    def __int__(self):
        return self._unpack(self._extract())

    def __hex__(self):
        """hex() needs a push."""
        return hex(int(self))

    def __iadd__(self, other):
        """Set bits from other in self."""
        new = int(self) | int(other)
        self.set_(new)
        return self

    def __isub__(self, other):
        """Clear bits from other in self."""
        new = int(self) & (~int(other))
        self.set_(new)
        return self

    def __contains__(self, other):
        """(v1[, v2 ...]) in self <=> all(lambda x: x in self, (v1[, v2 ...]))
        """
        all_ = 0x00
        try:
            for o in other:
                all_ |= int(o)
        except TypeError: # other is not iterable, unless some int(o) raised,
            all_ = int(other) # but if so this should raise too

        return int(self) == all_

    def __repr__(self):
        return ("<{} 0x{:x} 0b{:0"+str(self._length)+"b}>").format(self.name, int(self), int(self))

    def _extract(self):
        """return a self._length-long array from bitfield
        """
        return self._bitfield[self._start:self._end]

    def _store(self, bytes_):
        """set the bytes of length self._length in the bitfield
        """
        if not isinstance(bytes_, array):
            bytes_ = array('B', bytes_)
        assert len(bytes_) == self._length
        self._bitfield[self._start:self._end] = bytes_

    def _pad(self, bytes_):
        if self._length == self._fmt_size:
            return bytes_
        # must add padding bytes for struct.unpack
        pad = '\x00' * (self._fmt_size - self._length)
        if '<' in self._fmt:
            bytes_ = bytes_ + pad
        else:
            bytes_ = pad + bytes_
        return bytes_

    def _unpad(self, bytes_):
        if self._length == self._fmt_size:
            return bytes_
        # must remove padding bytes for struct.pack
        offset = self._fmt_size - self._length
        if '<' in self._fmt:
            return bytes_[:-offset]
        else:
            return bytes_[offset:]

    def _unpack(self, bytes_):
        """Return the data array as number.
        """
        data = _normalize_to_string(bytes_)
        assert len(data) == self._length
        data = self._pad(data)
        return struct.unpack(self._fmt, data)[0]

    def _pack(self, value):
        """Return value as array('B') of length self._length.
        """
        bytes_ = struct.pack(self._fmt, int(value))
        return self._unpad(bytes_)

class Flag(object):
    """A set of bitmasks within a bitfield.

    This may represent combinations of bit states between 8 and 64 bits long,
    instances are descriptors on Bitfield-s.

    """

    _bound_class = _BoundFlag

    def __init__(self, offset, length=None, fmt=None, mask=None, **choices):
        self._bound = {}
        self._choices = {}
        self._start = int(offset)
        self._length = 1
        if length is not None:
            assert length > 0 and length <= 8
            self._length = int(length)
        self._end = self._start + self._length
        if fmt is None:
            self._fmt = ARRAY_FORMAT[self._length]
        else:
            assert struct.calcsize(fmt) == \
                    struct.calcsize(ARRAY_FORMAT[self._length])
            self._fmt = fmt

        self._fmt_size = struct.calcsize(self._fmt)
        if choices:
            self._choices = dict([(k.lower(), v) for (k, v) in choices.iteritems()])

    def __getattr__(self, name):
        name = name.lower()
        if name in self._choices:
            return self._choices[name]
        raise AttributeError("{} has no attribute {}".format(self, name))

    @classmethod
    def _get_bound_instance(cls, self, bitfield):
        return cls._bound_class(bitfield, self)

    def _get_bound(self, bitfield):
        h = hash(bitfield)
        if h not in self._bound:
            self._bound[h] = self._get_bound_instance(self, bitfield)
        return self._bound[h]

    def __get__(self, bitfield, owner):
        if bitfield is None:
            return self
        return self._get_bound(bitfield)

    def __set__(self, bitfield, value):
        if bitfield is None:
            return
        b = self._get_bound(bitfield)
        b.set_(value)

class BooleanFlag(Flag):
    _size = 1
    class _bound_class(_BoundFlag):
        def __nonzero__(self):
            if int(self) == self.choices['true']:
                return True
            return False

    def __init__(self, offset=0, length=None, fmt=None, true=0x01, false=0x00):
        choices = dict(true=true, on=true, y=true, yes=true,
                       false=false, off=false, n=false, no=false)
        if true ^ false == 0x00:
            raise ValueError("Values for true and false must differ")

        super(BooleanFlag, self).__init__(offset, length, fmt, **choices)
        self._mask = true ^ false

class Bitfield(array):
    """Packs an array('B', ...) as a set of flags

    This can be any length and must be subclassed. Subclasses define
    ``cls._size`` to be the length of the bitfield in bytes and any
    number of instances of ``Flag`` as class attributes.

    The ``Flag`` instances provide the descriptor protocol and provide
    convenient access to values of various flag within the array.

    """
    _size = None
    def __new__(cls, data=None):
        if cls._size is None:
            raise RuntimeError("Subclasses of Bitfield should define _size")
        if data is None:
            data = [0] * cls._size
        elif len(data) != cls._size:
            raise RuntimeError("Unexpected data length for {}, got {}"
                               .format(cls, len(data)))
        bf = array.__new__(cls, 'B', data)
        bf.flags = {}
        for flag_name, flag in inspect.getmembers(
                          cls, lambda f: isinstance(f, Flag)):
            flag.name = flag_name
            bf.flags[flag_name] = flag
        return bf

    def __str__(self):
        return "<{} at 0x{:x} {}>".format(
                      self.__class__.__name__, hash(self),
                      ', '.join(['{}: 0x{:x}'.format(name, int(getattr(self, name)))
                                 for name in dir(self)
                                    if isinstance(getattr(self, name), _BoundFlag)]))

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__,
                             array.__repr__(self))
