import unittest

from . import test_util
from . import test_protocol
from . import camera

def offline():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_util))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_protocol))
    return suite

def all():
    suite = unittest.TestSuite()
    suite.addTest(offline())
    suite.addTest(camera.suite())
    return suite

suite = all