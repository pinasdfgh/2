from array import array
import unittest
from g3 import util

class TestBitfields(unittest.TestCase):

    def _get_bitfield_class(self):
        class FooBit(util.Bitfield):
            _size = 5
            first = util.Flag(0, 1, 'B', on=0x01, off=0x00, blinking=0x02)
            second = util.Flag(2, 2)
        return FooBit

    def test_bitfield_can_be_subclassed(self):
        self._get_bitfield_class()

    def test_blank_bitfield_can_be_instantiated(self):
        class_ = self._get_bitfield_class()
        foo = class_()
        self.assertEqual(array('B', foo), array('B', [0]*class_._size))

    def test_capture_params_can_be_extracted(self):
        from g3.protocol import ReleaseParams
        data = array('B', [32, 3, 1, 0, 100, 0, 0, 0, 1, 255, 0, 0, 3, 1, 3,
                           48, 0, 255, 0, 255, 0, 0, 0, 127, 255, 255, 64, 0,
                           40, 0, 112, 0, 24, 24, 255, 255, 24, 0, 56, 0, 230,
                           0, 154, 3, 230, 0, 32])
        foo = ReleaseParams(data)
        self.assertEqual(data.tostring(), foo.tostring())