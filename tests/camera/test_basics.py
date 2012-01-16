import unittest

from . import base
import time
class BasicCameraOperationsTest(base.BaseCameraTestCase):

    def test_time_can_be_read(self):
        t = self.cam.camera_time
        self.assertTrue(t is not None)


    def test_time_can_be_set(self):
        now = int(time.time())
        self.cam.camera_time = now
        self.assertLessEqual(self.cam.camera_time - now, 10)

if __name__ == '__main__':
    unittest.main()
