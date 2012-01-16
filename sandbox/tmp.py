import struct
from array import array
d = dict(
        RAW = (0x04, 0x02, 0x00),
        SMALL_NORMAL_JPEG = (0x02, 0x01, 0x02),
        SMALL_FINE_JPEG = (0x03, 0x01, 0x02),
        MEDIUM_NORMAL_JPEG = (0x02, 0x01, 0x01),
        MEDIUM_FINE_JPEG = (0x03, 0x01, 0x01),
        LARGE_NORMAL_JPEG = (0x02, 0x01, 0x00),
        LARGE_FINE_JPEG = (0x03, 0x01, 0x00),
        RAW_AND_SMALL_NORMAL_JPEG = (0x24, 0x12, 0x20),
        RAW_AND_SMALL_FINE_JPEG = (0x34, 0x12, 0x20),
        RAW_AND_MEDIUM_NORMAL_JPEG = (0x24, 0x12, 0x10),
        RAW_AND_MEDIUM_FINE_JPEG = (0x34, 0x12, 0x10),
        RAW_AND_LARGE_NORMAL_JPEG = (0x24, 0x12, 0x00),
        RAW_AND_LARGE_FINE_JPEG = (0x34, 0x12, 0x00))

for name, t in d.iteritems():
    i = (t[2]<<16) | (t[1]<<8) | (t[0])
    print "{}=0x{:x}, # {}".format(name, i, ["0x{:x}".format(n) for n in t])