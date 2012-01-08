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
from g3 import commands
from g3.util import hexdump

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