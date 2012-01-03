#!/usr/bin/bpython2 -i
"""Invoke this script in an interactive console for debugging

bpython2 -i sandbox.py
"""
import logging

import usb.core
import usb.control
import usb.util

import g3

cam = None

def init():
    global cam
    cam = g3.find()
    if not cam:
        return
    cam.initialize()
    cam.identify_camera()

if __name__ == '__main__':
    init()