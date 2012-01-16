import pcapy
from array import array

ENDPOINT_ADDR_MASK = 0x0f
ENDPOINT_DIR_MASK = 0x80
ENDPOINT_TRANSFER_TYPE_MASK = 0x03
CTRL_DIR_MASK = 0x80

def is_urb_submit(data):
    "match host-to-device packets"
    return data[0x08] == 'S'

def is_urb_complete(data):
    "match device-to-host packets"
    return data[0x08] == 'C'

def is_transfer_control(data):
    "match control transfer type"
    return (ord(data[0x09]) & ENDPOINT_TRANSFER_TYPE_MASK) == chr(0x02)

def is_transfer_bulk(data):
    "match bulk transfer type"
    return (ord(data[0x09]) & ENDPOINT_TRANSFER_TYPE_MASK) == chr(0x03)

def is_direction_in(data):
    "match IN transfers"
    return (ord(data[0x0a]) & ENDPOINT_DIR_MASK) == 0x80

def is_direction_out(data):
    "match OUT transfers"
    return (ord(data[0x0a]) & ENDPOINT_DIR_MASK) == 0x00


class CanonUSBCommand(object):
    def __init__(self, cmd1, cmd2, cmd3, serial, payload=None):
        self.cmd_1 = cmd1
        self.cmd_2 = cmd2
        self.cmd_3 = cmd3
        self.serial = serial
        self.payload = payload
        self.response = None

    @staticmethod
    def from_data(data):
        if not isinstance(data, array):
            data = array('B', data)

FILE = '/home/kiril/Desktop/G3/win_bootstrap.pcap'

def reader(filename):
    reader = pcapy.open_offline(filename)
    while True:
        try:
            yield reader.next()[1]
        except (StopIteration, pcapy.PcapError):
            raise StopIteration

def get_commands():
    cmds = []
    reader = pcapy.open_offline(FILE)
    def is_command_submit(data):
        return (is_transfer_control(data)
                    and is_direction_out(data)
                    and is_urb_submit(data))
    for data in reader(FILE):
        if is_command_submit(data):
            cmds.append(data)

    return cmds