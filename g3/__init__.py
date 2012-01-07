import sys
import logging
log = logging.getLogger(__name__)

log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())
logging.getLogger('usb').addHandler(logging.StreamHandler(sys.stderr))

from camera import Camera, G3Error
find = Camera.find