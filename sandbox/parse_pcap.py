import pcapy
from array import array

from canon import commands
from canon.util import le32toi, hexdump

ENDPOINT_ADDR_MASK = 0x0f
ENDPOINT_DIR_MASK = 0x80
ENDPOINT_TRANSFER_TYPE_MASK = 0x03
CTRL_DIR_MASK = 0x80

def is_urb_submit(data):
    "match host-to-device packets"
    return data[0x08] == ord('S')

def is_urb_complete(data):
    "match device-to-host packets"
    return data[0x08] == ord('C')

def is_transfer_control(data):
    "match control transfer type"
    return (data[0x09] & ENDPOINT_TRANSFER_TYPE_MASK) == 0x02

def is_transfer_bulk(data):
    "match bulk transfer type"
    return (data[0x09] & ENDPOINT_TRANSFER_TYPE_MASK) == 0x03

def is_direction_in(data):
    "match IN transfers"
    return (data[0x0a] & ENDPOINT_DIR_MASK) == 0x80

def is_direction_out(data):
    "match OUT transfers"
    return (data[0x0a] & ENDPOINT_DIR_MASK) == 0x00


class CanonUSBCommand(object):
    def __init__(self, cmd1=None, cmd2=None, cmd3=None, serial=None,
                 payload=None):
        self.cmd1 = cmd1
        self.cmd2 = cmd2
        self.cmd3 = cmd3
        self.serial = serial
        self.payload = payload
        self.response = array('B')

    @property
    def is_rc(self):
        return self.cmd1 == 0x13 and self.cmd2 == 0x12 and self.cmd3 == 0x201

    @staticmethod
    def from_out_packet(data):
        if not isinstance(data, array):
            data = array('B', data)
        assert len(data) >= 0x40
        request_size = data[0:4]
        cmd1 = data[0x44]
        cmd2 = data[0x47]
        cmd3 = le32toi(data, 4)
        serial = data[0x4c:0x50]
        return CanonUSBCommand(cmd1, cmd2, cmd3, serial, data[0x50:])

    def __repr__(self):
        if self.is_rc:
            name = (commands.lookup_rc(self.payload[0x00])
                        or '-RC 0x{:x}-'.format(self.payload[0x00]))
        else:
            name = commands.lookup(self.cmd1, self.cmd2, self.cmd3) or '-unknown-'
        name += '  ' + hexdump(self.payload[:0x10],
                        with_ascii=False, with_offset=False)
        return "<CMD 0x{:02x} 0x{:02x} 0x{:03x} (0x{:x}) {}>".format(
                                 self.cmd1, self.cmd2, self.cmd3,
                                 len(self.payload), name)


def reader(filename):
    reader = pcapy.open_offline(filename)
    while True:
        try:
            yield array('B', reader.next()[1])
        except (StopIteration, pcapy.PcapError):
            raise StopIteration

def is_cmd_start_packet(data):
    return all((
                is_transfer_control(data),
                is_direction_out(data),
                is_urb_submit(data)
                ))

def is_cmd_response_packet(data):
    return all((
                is_transfer_bulk(data),
                is_direction_in(data),
                is_urb_complete(data)
                ))

def get_commands(fname):
    cmds = []
    r = reader(fname)
    cmd = None
    for data in r:
        if is_cmd_start_packet(data):
            cmd = CanonUSBCommand.from_out_packet(data[0x40:])
            cmds.append(cmd)
        if is_cmd_response_packet(data):
            cmd.response.extend(data[0x40:])

    return cmds

if __name__ == '__main__':
    import sys
    fname = '/home/kiril/Desktop/G3/win_bootstrap.pcap'
    if len(sys.argv) > 1:
        fname = sys.argv[1]
    cmds = get_commands(fname)
    for i, c in enumerate(cmds):
        print i, c
        print hexdump(c.response)
        print