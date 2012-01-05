import struct
from array import array

def extract_string(data, start):
    end = data[start:].index(0x00)
    return data[start:start+end].tostring()

def itole32a(i):
    array('B', struct.pack('<I', i))

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

def dumphex(data):
    """Dump nicely printed binary data as hexadecimal text.
    """
    if type(data) is str:
        data = array.tostring()
    elif type(data) is unicode:
        data = array('u', data)

    out = ["%04x %s" % (row_idx*0x10,
                            ' '.join(("%02x"%x for x in row)))
            for row_idx, row
            in enumerate(chunks(data, 0x10))]

    return "\n".join(out)
