import time
import unittest

from .base import BaseCameraTestCase

class BasicCameraOperationsTest(BaseCameraTestCase):

    def test_time_can_be_read(self):
        t = self.cam.camera_time
        self.assertTrue(t is not None)

    def test_time_can_be_set(self):
        offset = self.cam.camera_time - time.time()
        self.cam.camera_time = 1300000000
        self.assertLessEqual(abs(self.cam.camera_time - 1300000000), 2)
        oldtime = offset + int(time.time())
        self.cam.camera_time = oldtime
        self.assertLessEqual(abs(self.cam.camera_time - oldtime), 2)

    def test_owner_can_be_read_and_written(self):
        owner = self.cam.owner
        self.cam.owner = "jus kiddin'"
        self.assertEqual(self.cam.owner, "jus kiddin'")
        self.cam.owner = owner
        self.assertEqual(self.cam.owner, owner)

if __name__ == '__main__':
    unittest.main()
