import sys
import logging
import os

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
_h = logging.StreamHandler(sys.stderr)
_h.setFormatter(logging.Formatter("%(created)-16.5f %(filename)s:%(lineno)-5s %(levelname)-6s %(message)s"))
log.addHandler(_h)


#_usb_log = logging.getLogger('usb')
#_usb_log.setLevel(logging.DEBUG)
#_usb_log.addHandler(_h)

from g3.camera import find

__all__ = ['find', 'log']