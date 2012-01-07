#!/usr/bin/bpython2 -i
"""Invoke this script in an interactive console for debugging

bpython2 -i sandbox.py
"""
import sys
import os
import logging
import threading
import time
from array import array
from pprint import pprint

import usb.core
import usb.control
import usb.util

import g3
from g3.util import hexdump

cam = None

class poll(object):
    def __init__(self, cam):
        self.cam = cam
        self.stop = False

    def __call__(self):
        try:
            while True:
                self.cam.usb._poll_interrupt(0x10)
                if self.stop:
                    return
                time.sleep(0.02)
        except Exception, e:
            print e
            return

def pt():
    t = threading.Thread(target=poll(cam))
    t.daemon = True
    return t

def init():
    global cam
    cam = g3.find()
    if not cam:
        return
    cam.initialize()

if __name__ == '__main__':
    init()