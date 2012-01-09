import unittest
from g3 import util

class TestBitfields(unittest.TestCase):

    def test_bitfield_instantiation(self):
        class FooBit(util.Bitfield):
            _size = 5
            first = util.Flag(0, 1, 'B', on=0x01, off=0x00, blinking=0x02)

        foo = FooBit()