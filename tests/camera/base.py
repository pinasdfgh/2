import time
import unittest

from canon import camera

class BaseCameraTestCase(unittest.TestCase):
    def setUp(self):
        self.cam = camera.find()
        for _ in xrange(3):
            try:
                self.cam.initialize(True)
                return
            except:
                time.sleep(2)

    def tearDown(self):
        self.cam.cleanup()
        del self.cam
