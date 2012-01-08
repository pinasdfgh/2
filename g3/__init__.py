import sys
import logging
log = logging.getLogger(__name__)

log.setLevel(logging.INFO)
_h = logging.StreamHandler(sys.stderr)
_h.setFormatter(logging.Formatter("%(created)-16.5f %(filename)s:%(lineno)s %(levelname)s %(message)s"))
log.addHandler(_h)

#logging.getLogger('usb').addHandler(_h)

from camera import Camera, G3Error
find = Camera.find