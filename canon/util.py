import struct
import string
from array import array
import inspect

def extract_string(data, start=0):
    try:
        end = data[start:].index(0x00)
    except (ValueError, IndexError):
        return None
    return data[start:start+end].tostring()

def le16toi(raw, start=None):
    raw = _normalize_array(raw)
    if start is not None:
        raw = raw[start:start+2]
    return struct.unpack('<H', raw)[0]

def le32toi(raw, start=None):
    raw = _normalize_array(raw)
    if start is not None:
        raw = raw[start:start+4]
    return struct.unpack('<I', raw)[0]

def itole32a(i):
    return array('B', struct.pack('<I', i))

def _normalize_array(raw):
    if type(raw) is array:
        raw = raw.tostring()
    elif type(raw) is str:
        pass
    else:
        raw = array('B', raw).tostring()
    return raw

def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def hexdump(data, with_ascii=True):
    """Dump nicely printed binary data as hexadecimal text.
    """
    if type(data) is str:
        data = array('B', data)
    elif type(data) is unicode:
        data = array('u', data)

    data = enumerate(chunks(data, 0x10)) # 16 bytes per line

    def format_row(idx, row):
        'Return a line represented in row'
        hextext = []
        for half in chunks(row, 8): # split the 16 bytes in the middle
            part = ' '.join("{:02x}".format(x) for x in half)
            hextext.append(part)

        hextext = '{:04x}  '.format(idx*0x10) + '  '.join(hextext)
        if not with_ascii:
            return hextext

        hextext = hextext.ljust(57) # adjust to 56 chars
        chartext = []
        for half in chunks(row, 8):
            chars = [(chr(c) if (chr(c) in string.ascii_letters
                                 or chr(c) in string.digits
                                 or chr(c) in string.punctuation
                                 or chr(c) == ' ')
                             else '.' if c == 0x00 else ';')
                     for c in half]
            part = ''.join(chars)
            chartext.append(part)
        hextext += ' '.join(chartext)
        return hextext

    out = [format_row(row_idx, row) for row_idx, row in data]

    return "\n".join(out)

class _BoundFlag(object):
    """An instance binging a ``Flag`` to a ``Bitfield``.
    """
    def __init__(self, bitfield, flag):
        self.bitfield = bitfield
        self.flag = flag
        self.start = flag.start
        self.end = flag.end
        self._pack = flag._pack
        self._unpack = flag._unpack

    @property
    def name(self):
        return self.flag.name

    def store(self, value):
        """Store the value in the bitfield."""
        value = self._pack(value)
        self.bitfield[self.start:self.end] = value

    def __int__(self):
        data = self.bitfield[self.start:self.end]
        return self._unpack(data)

    def __hex__(self):
        """hex() needs a push."""
        return hex(int(self))

    def __iadd__(self, other):
        """Set bits from other in self."""
        new = int(self) | int(other)
        self.store(new)
        return self

    def __isub__(self, other):
        """Clear bits from other in self."""
        new = int(self) & ~int(other)
        self.store(new)
        return self

    def __repr__(self):
        return ("<{} 0x{:x} 0b{:0"+str(self.flag.length)+"b}>").format(self.name, int(self), int(self))

class Flag(object):
    """A set of bitmasks within a bitfield.
    """

    _formats = [None, 'B', 'H', None, 'I', None, None, None, 'Q']

    def __init__(self, offset, length=None, fmt=None, **choices):
        self.start = offset
        self.length = 1
        if length is not None:
            assert length > 0 and length <= 8
            self.length = int(length)
        self.end = self.start + self.length
        if fmt is None:
            self.fmt = self._formats[self.length]
        else:
            assert struct.calcsize(fmt) == \
                    struct.calcsize(self._formats[self.length])
            self.fmt = fmt
        self._by_name = choices.copy()
        self._by_flag = dict((v,k) for (k,v) in choices.items())
        self._bound = {}

    def _get_bound(self, bitfield):
        h = hash(bitfield)
        if h not in self._bound:
            self._bound[h] = _BoundFlag(bitfield, self)
        return self._bound[h]

    def _unpack(self, data):
        data = _normalize_array(data)
        return struct.unpack(self.fmt, data)[0]

    def _pack(self, value):
        return array('B', struct.pack(self.fmt, value))

    def __get__(self, bitfield, owner):
        if bitfield is None:
            return self
        return self._get_bound(bitfield)

    def __set__(self, bitfield, value):
        b = self._get_bound(bitfield)
        b.store(value)

    def __delete__(self):
        raise RuntimeError("what?")

class Bitfield(array):
    """Packs an array('B', ...) as a set of flags

    This can be any length and must be subclassed. Subclasses define
    ``cls._size`` to be the length of the bitfield in bytes and any
    number of instances of ``Flag`` as class attributes.

    See ``Flag``.

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
