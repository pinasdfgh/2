import struct
import string
from array import array

def extract_string(data, start=0):
    try:
        end = data[start:].index(0x00)
    except:
        return None
    return data[start:start+end].tostring()

def itole32a(i):
    return array('B', struct.pack('<I', i))

def le32stoi(s):
    return struct.unpack('<I', s)[0]

def le32toi(raw):
    if type(raw) is array:
        raw = raw.tostring()
    elif type(raw) is str:
        pass
    else:
        raw = array('B', raw).tostring()
    return le32stoi(raw)

def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def hexdump(data, with_ascii=True):
    """Dump nicely printed binary data as hexadecimal text.
    """
    if type(data) is str:
        data = array.tostring()
    elif type(data) is unicode:
        data = array('u', data)

    data = enumerate(chunks(data, 0x10))

    def format_row(idx, row):
        hextext =  "%04x %s" % (row_idx*0x10,
                                ' '.join(("%02x"%x for x in row)))
        if with_ascii:
            hextext = hextext.ljust(54)
            chars = [(chr(c) if (chr(c) in string.ascii_letters
                                 or chr(c) in string.digits
                                 or chr(c) in string.punctuation
                                 or chr(c) == ' ')
                             else '.' if c == 0x00 else ';')
                     for c in row]
            hextext += ''.join(chars)
        return hextext

    out = [format_row(row_idx, row) for row_idx, row in data]

    return "\n".join(out)
