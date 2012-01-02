#!/usr/bin/env python2

import logging

import usb.core
import usb.control
import usb.util

import g3

cam = g3.find()
cam.initialize()
cam.identify_camera()