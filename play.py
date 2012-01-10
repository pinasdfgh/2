#!/usr/bin/bpython2 -i
"""Invoke this script in an interactive console for debugging

bpython2 -i sandbox.py
"""
import sys
import os
from usb.core import Device

if len(sys.argv) > 1:
    os.environ['PYUSB_DEBUG_LEVEL'] = sys.argv[1]

import logging
import threading
import time
from array import array
from pprint import pprint

import usb.core
import usb.control
import usb.util

import canon
from canon import protocol, util
from canon.util import hexdump

log = canon.log
log.info(" *** GAME STARTING ***")
log.info(" sys.argv: " + str(sys.argv))

canon.log.setLevel(logging.DEBUG)
#_h = logging.StreamHandler(open('play.log', 'a+'))
_h = logging.StreamHandler()
_h.setFormatter(logging.Formatter(
    "%(created)-16.5f %(filename)s:%(lineno)-5s %(levelname)-6s %(message)s"))
canon.log.addHandler(_h)

#_usb_log = logging.getLogger('usb')
#_usb_log.setLevel(logging.DEBUG)
#_usb_log.addHandler(_h)


cam = None

INFO = logging.INFO
DEBUG = logging.DEBUG

def lvl(ll):
    canon.log.setLevel(ll)

def init():
    global cam
    cam = canon.find()
    if not cam:
        return
    cam.initialize()

if __name__ == '__main__':
    init()