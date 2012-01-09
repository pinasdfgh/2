import sys
import logging
import os

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from g3.camera import find

__all__ = ['find', 'log']