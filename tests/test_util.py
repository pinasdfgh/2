from array import array
import unittest
from canon import util

class BitfieldTest(unittest.TestCase):

    def _get_bitfield_class(self):
        class FooBit(util.Bitfield):
            """
                  0        1        2        3        4
                  +--------+--------+--------+--------+--------+
                  | first  |        | second | second | third  |
                  +--------+--------+--------+--------+--------+
                  |        | over   | over   | over   |        |
                  +--------+--------+--------+--------+--------+

            """
            _size = 5
            first = util.Flag(offset=0, length=1, fmt='B',
                              on=0x01, off=0x02, blinking=0x04)
            second = util.Flag(2, 2)
            third = util.Flag(4, 1)
            over = util.Flag(1, 3, fight=0x44, meou=0x04, bark=0x40)

        return FooBit

    def _get_bitfield_instance(self, data=None, class_=None):
        if class_ is None:
            class_ = self._get_bitfield_class()
        return class_(data)

    def test_bitfield_can_be_subclassed_and_created(self):
        self._get_bitfield_instance()

    def test_bitfield_can_be_created_from_list(self):
        class_ = self._get_bitfield_class()
        foo = class_([0x05]*class_._size)
        self.assertEqual(foo, array('B', [0x05]*5))

    def test_setting_and_reading(self):
        foo = self._get_bitfield_instance([0x00]*5)
        foo.first = 0x7c
        self.assertEqual(int(foo.first), 0x7c)

    def test_raising_and_lowering_inplace_works(self):
        foo = self._get_bitfield_instance()

        self.assertEqual(int(foo.second), 0x0000)

        foo.second += 0x4040
        self.assertEqual(int(foo.second), 0x4040)

        foo.second -= 0x4000
        self.assertEqual(int(foo.second), 0x0040)

    def test_setting_and_reading_irregular_sized_flags(self):
        foo = self._get_bitfield_instance([0x11, 0x02, 0x13, 0x04, 0x15])
        self.assertEqual(0x11, int(foo.first))
        self.assertEqual(0x041302, int(foo.over), hex(foo.over))
        self.assertEqual(0x15, int(foo.third), hex(foo.third))

        foo.over = 0x7c4fc7
        self.assertEqual(0x7c4fc7, int(foo.over))
        self.assertEqual(0x7c4f, int(foo.second))
        self.assertEqual(foo[2:4], array('B', [0x4f, 0x7c]))

class UtilTest(unittest.TestCase):
    """TODO: this"""
    pass