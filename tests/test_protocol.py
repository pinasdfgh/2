import unittest
from array import array

class TestProtocolStructures(unittest.TestCase):

    def test_capture_params_can_be_extracted(self):
        from canon.capture import CaptureSettings
        data = array('B', [32, 3, 1, 0, 100, 0, 0, 0, 1, 255, 0, 0, 3, 1, 3,
                           48, 0, 255, 0, 255, 0, 0, 0, 127, 255, 255, 64, 0,
                           40, 0, 112, 0, 24, 24, 255, 255, 24, 0, 56, 0, 230,
                           0, 154, 3, 230, 0, 32])
        foo = CaptureSettings(data)
        self.assertEqual(data.tostring(), foo.tostring())


if __name__ == '__main__':
    unittest.main()
