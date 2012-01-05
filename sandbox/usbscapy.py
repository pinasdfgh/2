#!/usr/bin/env python
"""
Got this from 
http://comments.gmane.org/gmane.comp.security.scapy.general/4255
"""
import logging

import scapy
from scapy.fields import *
from scapy.packet import *
from scapy.automaton import Automaton, ATMT
from scapy.config import conf

from StateMachine import StateMachine

conf.debug_dissector = True
scapy.error.log_runtime.setLevel(logging.INFO)

conf.color_theme = scapy.config.themes.DefaultTheme()


### Monkeypatches
if not hasattr(scapy.fields, 'LEXShortEnumField'):
    class LEXShortEnumField(LEShortEnumField):
        def i2repr_one(self, pkt, x):
            if self not in conf.noenum and not isinstance(x,VolatileValue) and x in self.i2s:
                return self.i2s[x]
            return lhex(x)

if not hasattr(scapy.fields, 'StrFixedLenEnumField'):
    class StrFixedLenEnumField(StrFixedLenField):
        def __init__(self, name, default, length=None, enum=None, length_from=None):
            StrFixedLenField.__init__(self, name, default, length=length, length_from=length_from)
            self.enum = enum
        def i2repr(self, pkt, v):
            r = v.rstrip("\0")
            rr = repr(r)
            if v in self.enum:
                rr = "%s (%s)" % (rr, self.enum[v])
            elif r in self.enum:
                rr = "%s (%s)" % (rr, self.enum[r])
            return rr
        
if not hasattr(scapy.fields, 'LEXShortField'):
    class LEXShortField(LEShortField):
        def i2repr(self, pkt, x):
            return lhex(self.i2h(pkt, x))

if not hasattr(scapy.fields, 'IntLenField'):
    class IntLenField(LenField):
        def __init__(self, name, default):
            LenField.__init__(self, name, default, fmt="I")
if not hasattr(scapy.fields, 'LEIntLenField'):
    class LEIntLenField(LenField):
        def __init__(self, name, default):
            LenField.__init__(self, name, default, fmt="<I")

if not hasattr(scapy.fields, 'LEShortLenField'):
    class LEShortLenField(LenField):
        def __init__(self, name, default):
            LenField.__init__(self, name, default, fmt="<H")

if not hasattr(scapy.fields, 'UTF16LEStrField') or True:
    class CodecStrField(StrField):
        codec = 'ascii'
        def __init__(self, name, default, fmt="H", remain=0, codec=codec):
            #FIXME: Why doesn't this work?
            #         super(CodecStrField, self).__init__(name, default, fmt, remain)
            StrField.__init__(self, name, default, fmt, remain)
            self.codec = self.codec or codec
        def i2m(self, pkt, i):
            # That doesn't work for a weird reason:
            # return super(UTF16LEStrField, self).i2h(pkt, i.decode(self.codec, 'ignore'))
            return StrField.i2m(self, pkt, i.encode(self.codec, 'replace'))
        def m2i(self, pkt, m):
            if not isinstance(m, unicode):
                m = m.decode(self.codec, 'replace')
            return StrField.m2i(self, pkt, m)
        
    class UTF16LEStrField(CodecStrField):
        codec = 'utf_16_le'

if not hasattr(scapy.fields, 'ByteLenField'):
    class ByteLenField(LenField):
        def __init__(self, name, default):
            Field.__init__(self, name, default, fmt="B")




class PCapUSB(Packet):
    fields_desc = [
        StrFixedLenField('pcap_crap', 'A'*40, 40), # Check Documentation/usb/usbmon.txt which probably has details of the format 
    ]
class QemuUSB(Packet):
    DEVICETOHOST = 'D>H\x00'
    HOSTTODEVICE = 'H>D\x00'
    
    SETUP = 0b00101101
    IN    = 0b01101001
    OUT   = 0b11100001
    
    ATTACH = 0x100
    DETACH = 0x101
    RESET  = 0x102

    name = 'QemuUSB'
    fields_desc = [
        StrFixedLenEnumField('pipe_direction', DEVICETOHOST, 4, {DEVICETOHOST: 'device to host',
                                                                 HOSTTODEVICE: 'host to device'}),
        LEIntEnumField('pid', 'SETUP', {'SETUP': SETUP, 'IN': IN, 'OUT': OUT,
                                        'ATTACH': ATTACH, 'DETACH': DETACH, 'RESET': RESET}),
        ByteField('devaddr', 0),
        ByteField('devep', 0),
        LEIntLenField('length', None),
    ]
    
    @classmethod
    def from_file(cls, fd):
        packet_data = fd.read(len(QemuUSB()))
        if packet_data == "":
            raise EOFError()
        packet = QemuUSB(packet_data)
        rest_length = packet.length
        if rest_length > 0:
            rest_of_packet = fd.read(rest_length)
            full_packet = QemuUSB(packet_data + rest_of_packet)
        else:
            full_packet = QemuUSB(packet_data)
        print 'I AM RECEIVER %r' % full_packet
        return full_packet

    def to_file(self, fd):
        packet = str(self)
        initial_length = len(QemuUSB())
        cut_off = len(self)
        self.show()
        packet, remain = packet[:initial_length], packet[initial_length:initial_length+cut_off] 
        written = fd.write(packet)
        print 'Trying to write'
        # Maybe repalce self.length with len(self)
        written = fd.write(remain)
        fd.flush()
        print 'written %u (%u): %s' % (len(packet)+len(remain), len(remain), packet.encode('hex') + remain.encode('hex'))
        return written
    
    def same_as_wo_data(self, other):
        '''Compares another QemuUSB packet without the data. For legacy reasons.'''
        s1 = self.copy()
        s2 = other.copy()
        s1.payload = None
        s2.payload = None
        return s1 == s2
            

class USBIn(Packet):
    name = 'USBIn'

    fields_desc = [
    ]

class USBOut(Packet):
    name = 'USBOut'

    fields_desc = [
    ]

REQUEST_ENUM = {
    'GET_STATUS': 0x00, 'CLEAR_FEATURE': 0x01,
    'SET_FEATURE': 0x03,                       'SET_ADDRESS':  0x05, 
    'GET_DESCRIPTOR': 0x06, 'SET_DESCRIPTOR': 0x07, 'GET_CONFIGURATION': 0x08,
    'SET_CONFIGURATION': 0x09,
}

def is_get_descriptor(pkt):
    return     (pkt.haslayer(USBSetup)      \
            and pkt.type == USBSetup.TYPE_STANDARD           \
            and pkt.request == USBSetup.REQUEST_ENUM['GET_DESCRIPTOR'] \
            )
    
def is_get_descriptor_request(pkt):
    is_get_descriptor = pkt.haslayer(USBSetup) and pkt.request == REQUEST_ENUM['GET_DESCRIPTOR'] and pkt.data_xfer_direction == USBSetup.DIR_DEVICE_TO_HOST
    if is_get_descriptor == True:
        pkt.value = pkt.descriptor_type << 8 | pkt.descriptor_index
    return is_get_descriptor

def is_get_device_descriptor_request(pkt):
    retval = is_get_descriptor_request(pkt) and (pkt.descriptor_type == USBSetup.DESCRIPTOR_TYPES['Device'])
    if retval:
        print 'Here be device descriptors', pkt.show()
    return retval

def is_get_configuration_descriptor_request(pkt):
    return is_get_descriptor_request(pkt) and (pkt.descriptor_type == USBSetup.DESCRIPTOR_TYPES['Configuration'])

def is_get_interface_descriptor_request(pkt):
    
    return is_get_descriptor_request(pkt) and (pkt.descriptor_type == USBSetup.DESCRIPTOR_TYPES['Interface'])

def is_get_string_descriptor_request(pkt):
    return is_get_descriptor_request(pkt) and (pkt.descriptor_type == USBSetup.DESCRIPTOR_TYPES['String'])

def is_set_address_request(pkt):
    is_set_address = pkt.haslayer(USBSetup) and pkt.request == REQUEST_ENUM['SET_ADDRESS'] and pkt.data_xfer_direction == USBSetup.DIR_HOST_TO_DEVICE
    is_set_address = is_set_address and pkt.index == 0 and pkt.getlayer(USBSetup).length == 0
    return is_set_address

def is_set_configuration_request(pkt): # USB 9.4.7 p.257
    print pkt.show()
    is_set_configuration = pkt.haslayer(USBSetup) and pkt.request == REQUEST_ENUM['SET_CONFIGURATION'] and pkt.data_xfer_direction == USBSetup.DIR_HOST_TO_DEVICE
    is_set_configuration = is_set_configuration and pkt.index == 0 and pkt.getlayer(USBSetup).length ==0
    print is_set_configuration, pkt.show()
    return is_set_configuration

class USBSetup(Packet):
    name = 'USBSetup'

    DIR_HOST_TO_DEVICE = 0
    DIR_DEVICE_TO_HOST = 1
    
    TYPE_STANDARD = 0
    TYPE_CLASS    = 1
    TYPE_VENDOR   = 2
    TYPE_RESERVED = 3
    
    REC_DEVICE      = 0
    REC_INTERFACE   = 1
    REC_ENDPOINT    = 2
    REC_OTHER       = 3
    
    REQUEST_ENUM = REQUEST_ENUM
    
    DESCRIPTOR_TYPES = {
            'Device': 1, 'Configuration': 2, 'String': 3,
            'Interface': 4, 'Endpoint': 5, 'Device Qualifier': 6,
            'Other Speed Configuration': 7, 'Interface Power': 8,
        }
    
    
    fields_desc = [
        BitEnumField('data_xfer_direction', 0, 1, { DIR_HOST_TO_DEVICE: 'Host-to-device', DIR_DEVICE_TO_HOST: 'Device-to-host'}),
        BitEnumField('type', 0, 2, { TYPE_STANDARD: 'Standard', TYPE_CLASS: 'Class', TYPE_VENDOR: 'Vendor', TYPE_RESERVED: 'Reserved'}),
        BitEnumField('recipient', 0, 5, { REC_DEVICE: 'Device', REC_INTERFACE: 'Interface', REC_ENDPOINT: 'Endpoint', REC_OTHER: 'Other'}),
        ByteEnumField('request', 0, REQUEST_ENUM),
        ConditionalField(
                         LEShortField('value', 0),
                         lambda x: not is_get_descriptor_request(x)),
        ConditionalField(
                         ByteField('descriptor_index', 0),
                         lambda x: is_get_descriptor_request(x)),
        ConditionalField(
                         ByteEnumField('descriptor_type', 1, DESCRIPTOR_TYPES), 
                         lambda x: is_get_descriptor_request(x)),
                         
#                         lambda pkt: pkt.getlayer(USBSetup).request != REQUEST_ENUM['GET_DESCRIPTOR']),
#                          lambda pkt: True),
        LEShortField('index', 0),
        LEShortField('length', 0), # Number of bytes to transfer if there is$
    ]
    
    packets = scapy.plist.PacketList(name='Setups')
    
    def __init__(self, *args, **kwargs):
        super(USBSetup, self).__init__(*args, **kwargs)
        
    def post_dissect(self, p):
        print 'Appending to mah packets'
        USBSetup.packets.append(self)
        print 'new packets %r' % USBSetup.packets
        p = super(USBSetup, self).build_done(p)
        return p
    
    @classmethod
    def get_last_packet(cls):
        try:
            last = cls.packets[-1]
        except IndexError:
            last = None
        return last

DEVICECLASS_ENUMS = { # http://www.usb.org/developers/defined_class
    'Base Class': 0x00, 
    'Communications': 0x02,
    'Hub': 0x09,
    'Diagnostic': 0x42,
    'Misc': 0xEF,
    'Application Specific': 0xFE,
    'Vendor Specified': 0xFF,
}
DEVICESUBCLASS_ENUMS = {
    0x01: 'Freezing',
    0x23: 'Warm',
    0x42: 'Nonfunction',
    0xFF: 'Dunno',
}
DEVICEPROTOCOL_ENUMS = {
    0x01: '1',
    0x23: '2',
    0x42: '3',
    0xFF: '4',
}
VENDOR_ENUMS = {
    0x0001: '1',
    0x0023: '2',
    0x0042: '3',
    0xFFFF: '4',
}

class USBInDeviceDescriptor(Packet):
    name = 'DeviceDescriptor'

    fields_desc = [
        LEXShortField('bcdUSB', 0x0200),
        ByteEnumField('bDeviceClass', 0, DEVICECLASS_ENUMS),
        ByteEnumField('bDeviceSubClass', 0, DEVICESUBCLASS_ENUMS),
        ByteEnumField('bDeviceProtocol', 0, DEVICEPROTOCOL_ENUMS),
        ByteField('bMaxPacketSize', 64),
        LEXShortEnumField('idVendor', 0xffff, VENDOR_ENUMS),
        LEXShortField('idProduct', 0xffff),
        LEShortField('bcdDevice', 0x0815),
        ByteField('iManufacturer', 0),
        ByteField('iProduct', 0),
        ByteField('iSerialNumber', 0),
        ByteField('bNumConfigurations', 0),
    ]
    
    


class USBInEndpointDescriptor(Packet):
    name = 'InterfaceDescriptor'

    CLASS_ENUM = {
            'Nutting':0x00 ,
            'Mass Storage':0x01,
        }
    SUBCLASS_ENUM = {
            'Nutting':0x00 ,
        }
    fields_desc = [
        BitEnumField('endpoint_direction', 0, 1, {'Out': 0, 'In':1,}),
        BitEnumField('endpoint_reserved0', 0, 3, {'Correct': 0, 'Wrong':1,'Wrong':2,'Wrong':3,'Wrong':4,'Wrong':5,'Wrong':6,'Wrong':7,'Wrong':8, }),
        BitField('endpoint_number', 0, 4),
        
        BitField('reserved0', 0, 2),
        BitEnumField('usage_mode', 0, 2, ('Data', 'Feedback', 'Explicit Feedback', 'Reserved')),
        BitEnumField('sync_type', 0, 2, ('None', 'Async', 'Adaptive', 'Sync')),
        BitEnumField('transfer_type', 0, 2, ('Control', 'Isochronous', 'Bulk', 'Interrupt')),
        
        LEShortField('wMaxPacketSize', 64), # Maximum Packet Size this endpoint is capable of sending or receiving
        ByteField('bInterval', 255), # Interval for polling endpoint data transfers. Value in frame counts. Ignored for Bulk & Control Endpoints. Isochronous must equal 1 and field may range from 1 to 255 for interrupt endpoints
    ]
    
    def extract_padding(self, pay):
        return "", pay

class USBInInterfaceDescriptor(Packet):
    name = 'InterfaceDescriptor'

    CLASS_ENUM = {
            'Audio': 0x01,
            'Communications': 0x02,
            'HID': 0x03,
            'Physical': 0x05,
            'Image': 0x06,
            'Printer': 0x07,
            'Mass Storage': 0x08,
            'CDC-Data ': 0x0A,
            'Smart Card': 0x0B,
            'Content Security': 0x0D,
            'Video ': 0x0E,
            'Personal Healthcare': 0x0F,
            'Diagnostic Device': 0xDC,
            'Wireless Controller ': 0xE0,
            'Miscellaneous': 0xEF,
            'Application Specific': 0xFF,
            'Vendor Specific': 0xFF,
        }
    SUBCLASS_ENUM = {
            'Nutting':0x00 ,
        }
    fields_desc = [
        ByteField('bInterfaceNumber', 1),       # Number of Interface
        ByteField('bAlternateSetting', 0),  # Value used to select alternative setting
        ByteField('bNumEndpoints', None), # Number of Endpoints used for this interface
        ByteEnumField('bInterfaceClass', CLASS_ENUM['Mass Storage'], CLASS_ENUM), # Class Code (Assigned by USB Org)
        ByteEnumField('bInterfaceSubClass', 0, SUBCLASS_ENUM), # Subclass Code (Assigned by USB Org)
        ByteField('bInterfaceProtocol', 0), # Protocol Code (Assigned by USB Org)
        ByteField('iInterface', 0), # Index of String Descriptor Describing this interface
    ]
    
    def extract_padding(self, pay):
        return "", pay

class USBInStringDescriptor(Packet):
    name = 'StringDescriptor'
    
    LANGUAGE_ENUM = {'English-US': 0x0409, 'German-Standard': 0x0407}
    
    fields_desc = [
                   FieldListField('Languages', 0x0409,
                                        LEXShortEnumField('Code', 0x0409, LANGUAGE_ENUM),
                                        count_from=lambda pkt: pkt[USBInStringDescriptor].get_field_count()),
    ]
    
    def get_field_count(self):
        BYTES_PER_LANGUAGE = 2
        transport_layer = self.underlayer
        if transport_layer:
            packet_length = transport_layer.length
            transport_layer_header_length = 2
            nr_langs = (packet_length - 
                        transport_layer_header_length) / BYTES_PER_LANGUAGE
        else:
            langs = self.fields.get('Languages', [])
            nr_langs = len(langs) / BYTES_PER_LANGUAGE
        return nr_langs
    
class USBString(Packet):
    name = 'String'
    
    fields_desc = [
        UTF16LEStrField('string', 'foo'),
    ]
    
    def __init__(self, *args, **kwargs):
        super(USBString, self).__init__(*args, **kwargs)
        
        self.index = None
        self.descriptor_index = None
        
        be_stateful = True # The idea is to make this a global configuration
        if be_stateful:
            last_setup = USBSetup.get_last_packet()
            if last_setup is not None and is_get_string_descriptor_request(last_setup):
                self.index = last_setup[USBSetup].index
                self.descriptor_index = last_setup[USBSetup].descriptor_index
    
    @staticmethod
    def string_encode(s):
        '''Returns a proper USB encoded string (UCS2 but UTF16LE)'''
        return s.encode('utf_16_le')
     
    def set_string(self, s):
        '''Applies proper USB encoding to a given string and sets it''' 
        self.string = USBString.string_encode(s)
    
    def answers_available_languages(self):
        '''Returns whether this packet represents supported languages
        
        The USB host can ask the device for a packet full of supported
        languages by setting index and descriptor_index to 0.
        This function assumes that self has those fields and checks them.
        ''' 
        is_languages_requested = self.descriptor_index == 0 and self.index == 0
        return is_languages_requested



class USBInDescriptor(Packet):
    name = 'Descriptor'
    
    TYPE_ENUM = { 'Device': 0x01, 'Configuration': 0x02,
                  'String': 0x03, 'Interface': 0x04,
                  'Endpoint': 0x05,
                  'HID': 0x22, 'HIDReport': 0x22  }


    fields_desc = [
        ByteField('length', None),
        ByteEnumField('type', 0x01, TYPE_ENUM),
    ]
    
    def guess_payload_class(self, payload):
        TYPE_ENUM = self.TYPE_ENUM
        TYPE_TO_CLASS = {
                         TYPE_ENUM['Device'] : USBInDeviceDescriptor,
                         TYPE_ENUM['Configuration'] : USBInConfigurationDescriptor,
                         TYPE_ENUM['String'] : USBString,
                         TYPE_ENUM['Interface'] : USBInInterfaceDescriptor,
                         TYPE_ENUM['Endpoint'] : USBInEndpointDescriptor,
                         TYPE_ENUM['HID'] : USBInDeviceDescriptor,
                         }
        this_type = self.type
        cls = TYPE_TO_CLASS.get(this_type, None)
        last_setup = USBSetup.get_last_packet()
        if last_setup:
            index = last_setup[USBSetup].index
            descriptor_index = last_setup[USBSetup].descriptor_index
            if this_type == self.TYPE_ENUM['String'] and index == 0 and descriptor_index == 0:
                cls = USBInStringDescriptor
        
        return cls or self.default_payload_class(payload)

    def post_build(self, pkt, pay):
        '''Adjust the length field, because there is no such thing as "whole packet len field"'''
        if self.length is None:
            offset = 0
            value = len(pkt) & 0xFF
            value += len(pay)
            pkt = pkt[:offset] + chr(value) + pkt[offset+1:]
        return pkt+ pay

class USBInConfigurationDescriptor(Packet):
    name = 'ConfigurationDescriptor'

    fields_desc = [
        LEShortLenField('wTotalLength', None), # Total length in bytes of data returned
        ByteField('bNumInterfaces', None),       # Number of Interfaces #FIXME: This should be possible to automate.
        ByteField('bConfigurationValue', 1),  # Value to use as an argument to select this configuration
        ByteField('iConfiguration', 0), # Index of String Descriptor describing this configuration
        BitEnumField('Reserved1', 1, 1, {'Correct': 1, 'Wrong': 0}),
        BitEnumField('selfpowered', 1, 1, {'True': 1, 'False': 0}),
        BitEnumField('remotewakeup', 1, 1, {'True': 1, 'False': 0}),
        BitEnumField('Reserved0', 0, 5, {'Correct': 0, 'Wrong': 1}),
        ByteField('bMaxPower', 255), # Maximum Power Consumption in 2mA units
#        ConditionalField(
                         PacketListField('descriptors', None, USBInDescriptor, length_from = lambda pkt: pkt.wTotalLength - len(USBInConfigurationDescriptor())),
#                         lambda pkt: True,
#                         )
    ]
    
    def post_build(self, pkt, pay):
        '''Adjusts the length of the whole packet (wTotalLength) and the bNumInterfaces''' 
        if self.wTotalLength is None:
            offset = 0
            value = len(pkt) & 0xFF
            pkt = pkt[:offset] + chr(value) + pkt[offset+1:]
            offset = 1
            value = (len(pkt)>>8) & 0xFF
            pkt = pkt[:offset] + chr(value) + pkt[offset+1:]
        
        if self.bNumInterfaces is None:
            numInterfaces = sum(map(lambda x: isinstance(x.payload, USBInInterfaceDescriptor), self.descriptors))
            print 'found %d interfaces' % numInterfaces
            offset = 0+1+1
            value = numInterfaces
            pkt = pkt[:offset] + chr(value) + pkt[offset+1:]
            
        # FIXME: Build bNumEndpoints or so in Interfacedescriptor
        return pkt+ pay
    
    def extract_padding(self, pay):
        return "", pay

#bind_bottom_up(PCapUSB, USBSetup,)
#bind_top_down(PCapUSB, USBSetup, pid = 0b00101101)
#bind_bottom_up(PCapUSB, USBIn,)
#bind_top_down(PCapUSB, USBIn, pid = 0b11100001)
#bind_bottom_up(PCapUSB, USBOut,)
#bind_top_down(PCapUSB, USBOut, pid = 0b01101001)
#scapy.config.conf.l2types.register(0xdc, PCapUSB)

bind_layers(QemuUSB, USBSetup, pid = 0b00101101)
bind_layers(QemuUSB, USBOut,   pid = 0b11100001)
bind_layers(QemuUSB, USBIn,    pid = 0b01101001)


bind_layers(USBIn,  USBInDescriptor) # This unconditional binding is only temporary

bind_top_down(USBInDescriptor, USBInDeviceDescriptor, type=USBInDescriptor.TYPE_ENUM['Device'])
bind_top_down(USBInDescriptor, USBInConfigurationDescriptor, type=USBInDescriptor.TYPE_ENUM['Configuration'])
bind_top_down(USBInDescriptor, USBInInterfaceDescriptor, type=USBInDescriptor.TYPE_ENUM['Interface'])
bind_top_down(USBInDescriptor, USBInEndpointDescriptor, type=USBInDescriptor.TYPE_ENUM['Endpoint'])
bind_top_down(USBInDescriptor, USBString, type=USBInDescriptor.TYPE_ENUM['String'])
bind_top_down(USBInDescriptor, USBInStringDescriptor, type=USBInDescriptor.TYPE_ENUM['String'])

class USB_MSD_CBW(Packet):
    '''See USB mass storage: designing and programming devices and embedded hosts Von Jan Axelson p. 74ff'''
    field_desc = [
        IntField('dCBWSignature', 0x43425355),
        IntField('dCBWTag', 23),
        IntField('dCBWDataTransferLength', 42),
        ByteField('bCBWFlags', 3),
        BitField('reserved0', 4, 0),
        BitField('bCBWLUN', 4, 0),
        BitField('reserved0', 3, 0),
        BitField('bCBWCBLength', 4, 0),
    ]
        
class USB_MSD_CSW(Packet):
    '''See USB mass storage: designing and programming devices and embedded hosts Von Jan Axelson p. 78ff'''
    field_desc = [
        IntField('dCBWSignature', 0x43425355),
        IntField('dCBWTag', 23),
        IntField('dCSWDataResidue', 42),
        ByteField('bCSWStatus', 3),
    ]
#bind_layers(USB_MSD_CBW, USB_CBWCB)








def replace_bind_layers(From, To, **kwargs):
    print 'replacing binding'
    From.payload_guess = []
    bind_layers(From, To, **kwargs)

USBHEADERLENGTH = 4+4+1+1+4
USBHEADERLENGTH = len(QemuUSB())




class USBParser(StateMachine):
    def __init__(self, data):
        StateMachine.__init__(self)
        self.data = data
        self.packets = []
        
    def get_last_packet(self):
        self.packets[-1]

    def __iter__(self):
        return self

    def next(self):
        if len(self.data) >= USBHEADERLENGTH:
            foo = QemuUSB(self.data[:USBHEADERLENGTH])
            #print [ord(c) for c in data[:USBHEADERLENGTH]], foo.length
            packet, self.data = self.data[:foo.length + USBHEADERLENGTH], self.data[foo.length + USBHEADERLENGTH:]
            print 'dissecting package'
            self.current_packet = QemuUSB(packet)

            print 'state', self._current_state, 'type of packet', type(self.current_packet.payload)
            self.schedule_once()

            return self.current_packet
        else:
            raise StopIteration()

    @StateMachine.start
    def begin(self):
        pkt = self.current_packet
        if not (self.current_packet.pipe_direction == QemuUSB.HOSTTODEVICE):
            return 'begin'
        else:
            if isinstance(pkt.payload, USBSetup):
                if is_get_string_descriptor_request(pkt):
    #                print 'Looking at index of', pkt.show(), pkt.payload.index==0
                    if pkt.payload.index == 0:
    #                    print 'Replacing Layers', pkt.show()
                        print 'Replacing for InString'
                        replace_bind_layers(USBInDescriptor, USBInStringDescriptor)
                    else:
    #                    print 'Mah Index', pkt.index
    #                    raise pkt.index
                        print 'Replacing for regualr String'
                        replace_bind_layers(USBInDescriptor, USBString)
                    return 'begin'
                return 'expecting_device_descriptor'
            else:
                return 'begin'

    @StateMachine.state
    def expecting_device_descriptor(self):
        if self.current_packet.pipe_direction == QemuUSB.HOSTTODEVICE:
#            replace_bind_layers(USBIn, USBInDescriptor)
            return 'begin'
        else:
#            replace_bind_layers(USBIn, USBInDescriptor) #FIXME: Use the next expected class
            return 'begin'


def test():
    import binascii
    filename = 'massstorage-full.dump'
    filename = 'webcam.dump'
    allowed_directions = (
                          QemuUSB.DEVICETOHOST,
                          QemuUSB.HOSTTODEVICE,
                          )
    qp = USBParser(file(filename, 'r').read())
    for packet in qp:
        for direction in allowed_directions:
            if packet.pipe_direction == direction:
                print repr(packet)
#                print packet.command()
                print binascii.hexlify(str(packet.payload)) if packet.pipe_direction == QemuUSB.DEVICETOHOST else None 

def bla():
    print [hex(ord(x)) for x in hexdump]
    p = QemuUSB(hexdump)
    print repr(p) #, p.fields, 'pid' in p.fields
    print p.getfieldval('pid')
    print [ord(c) for c in p.getfieldval('pipe_direction')]
    #print len(p.payload), repr(p.payload), len(p)
    #print dir(p)


if __name__ == '__main__':
    test()
