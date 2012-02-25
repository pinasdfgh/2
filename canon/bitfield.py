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

from array import array
from canon.util import _normalize_to_string, ARRAY_FORMAT
import struct
import inspect

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
        data = self._pack(value)
        self._store(data)

    def __int__(self):
        return self._unpack(self._extract())

    def __hex__(self):
        """hex() needs a push."""
        return hex(int(self))

    def __iadd__(self, other):
        """Set bits from other in self, self |= other"""
        new = int(self) | int(other)
        self.set_(new)
        return self

    def __isub__(self, other):
        """Clear bits from other in self, self &= ^other """
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

    def _extract(self):
        """return a self._length-long array from bitfield
        """
        return self._bitfield[self._start:self._end]

    def _store(self, data):
        """set the bytes of length self._length in the bitfield
        """
        if not isinstance(data, array):
            data = array('B', data)
        assert len(data) == self._length
        self._bitfield[self._start:self._end] = data

    def _pad(self, data):
        if self._length == self._fmt_size:
            return data
        # must add padding bytes for struct.unpack
        pad = '\x00' * (self._fmt_size - self._length)
        if '<' in self._fmt:
            data = data + pad
        else:
            data = pad + data
        return data

    def _unpad(self, data):
        if self._length == self._fmt_size:
            return data
        # must remove padding bytes for struct.pack
        offset = self._fmt_size - self._length
        if '<' in self._fmt:
            return data[:-offset]
        else:
            return data[offset:]

    def _unpack(self, data):
        """Return the data array as number.
        """
        data = _normalize_to_string(data)
        assert len(data) == self._length
        data = self._pad(data)
        return struct.unpack(self._fmt, data)[0]

    def _pack(self, value):
        """Return value as array('B') of length self._length.
        """
        data = struct.pack(self._fmt, int(value))
        return self._unpad(data)

    def __getattr__(self, name):
        return getattr(self._flag, name)

    def __repr__(self):
        return ("<{} {} 0b{:0"+str(self._length)+"b}>").format(
                   self.name, self._flag.get_value_name(int(self)), int(self))


class Flag(object):
    """A set of bitmasks within a bitfield.

    This may represent combinations of bit states between 8 and 64 bits long,
    instances are descriptors on Bitfield-s.

    """

    _bound_class = _BoundFlag

    def __init__(self, offset, length=None, fmt=None, **choices):
        """
        ``offset``
            in bytes, from the beginning of the bitfield.
        ``length``
            in bytes, between 1 and 8, defaults to 1.
        ``fmt``
            the formatting character for pack/unpack. Only specify if
            something exotic, ``ARRAY_FORMAT`` has sensible defaults.
        ``choices``
            contains a map of human-readable labels of different values.

        """
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

    def get_value_name(self, value):
        for k, v in self._choices.iteritems():
            if v == value:
                return k
        return '<unknown 0x{:x}>'.format(value)

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
            if int(self) == self._choices['true']:
                return True
            return False
        def set_(self, value):
            if isinstance(value, bool):
                value = (self._choices['true']
                         if value
                         else self._choices['false'])
            data = self._pack(value)
            self._store(data)

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

    The ``Flag`` instances provide the descriptor protocol and
    convenient access to values of various flag within the array.
    The bytes they represent are defined by their ``offset`` and
    ``length`` constructor arguments, ``Flag`` instances can overlap
    within a bitfield, but that's probably to be avoided unless absolutely
    necessary.

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

    def __repr__(self):
        bounds = []
        for name in self.flags:
            bounds.append(getattr(self, name))
        return "<{} at 0x{:x} {}>".format(
                      self.__class__.__name__, hash(self),
                      ', '.join(['{}'.format(str(bound))
                                 for bound in bounds]))

