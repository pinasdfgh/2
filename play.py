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

import g3
from g3 import protocol, util
from g3.util import hexdump

log = g3.log
log.info(" *** GAME STARTING ***")
log.info(" sys.argv: " + str(sys.argv))

g3.log.setLevel(logging.DEBUG)
#_h = logging.StreamHandler(open('play.log', 'a+'))
_h = logging.StreamHandler()
_h.setFormatter(logging.Formatter(
    "%(created)-16.5f %(filename)s:%(lineno)-5s %(levelname)-6s %(message)s"))
g3.log.addHandler(_h)

#_usb_log = logging.getLogger('usb')
#_usb_log.setLevel(logging.DEBUG)
#_usb_log.addHandler(_h)


cam = None

INFO = logging.INFO
DEBUG = logging.DEBUG

def lvl(ll):
    g3.log.setLevel(ll)

def init():
    global cam
    cam = g3.find()
    if not cam:
        return
    cam.initialize()

if __name__ == '__main__':
    init()