#!/usr/bin/env python2

import logging

import usb.core
import usb.util
import usb.control

logging.basicConfig()

G3_USB_VENDORID = 0x04a9
G3_USB_PRODUCTID = 0x306e

def g3_get():
    dev = usb.core.find(idVendor=G3_USB_VENDORID, idProduct=G3_USB_PRODUCTID)
    return dev

def g3_init(g3):
    g3.set_configuration()
    g3.set_interface_altsetting()
    r = g3.ctrl_transfer(0xc0, 12, wValue=0x55, wIndex=0, data_or_wLength=1)
    print r
    r2 = g3.ctrl_transfer(0xc0, 4, 0x01, data_or_wLength=0x58)
    print r2

# set the active configuration. With no arguments, the first
# configuration will be the active one
#dev.set_configuration()
#
## get an endpoint instance
#cfg = dev.get_active_configuration()
#interface_number = cfg[(0,0)].bInterfaceNumber
#alternate_settting = usb.control.get_interface(interface_number)
#intf = usb.util.find_descriptor(
#    cfg, bInterfaceNumber = interface_number,
#    bAlternateSetting = alternate_setting
#)
#
#ep = usb.util.find_descriptor(
#    intf,
#    # match the first OUT endpoint
#    custom_match = \
#    lambda e: \
#        usb.util.endpoint_direction(e.bEndpointAddress) == \
#        usb.util.ENDPOINT_OUT
#)
#
#assert ep is not None
#
## write the data
#ep.write('test')
