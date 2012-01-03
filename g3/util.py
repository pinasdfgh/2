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