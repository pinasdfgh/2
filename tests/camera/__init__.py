import unittest

import test_basics, test_storage

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_basics))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_storage))
    return suite

if __name__ == '__main__':
    unittest.main()
