import sys
import logging
import os

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class CanonError(Exception): pass
