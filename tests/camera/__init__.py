import unittest

from . import test_basics
from . import test_storage

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_basics))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_basics))
    return suite