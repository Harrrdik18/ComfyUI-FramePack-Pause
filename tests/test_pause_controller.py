import threading
import time
import unittest

from pause_controller import PauseController


class PauseControllerTests(unittest.TestCase):
    def test_starts_running(self):
        self.assertFalse(PauseController().snapshot()["paused"])

    def test_pause_blocks_until_resume(self):
        controller = PauseController()
        controller.pause()
        entered = threading.Event()
        finished = threading.Event()

        def worker():
            entered.set()
            controller.wait_if_paused()
            finished.set()

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(entered.wait(1))
        time.sleep(0.05)
        self.assertFalse(finished.is_set())
        controller.resume()
        self.assertTrue(finished.wait(1))
        thread.join(timeout=1)

    def test_sampler_loop_status(self):
        controller = PauseController()
        with controller.sampler_loop(12):
            controller.set_step(4, 12)
            state = controller.snapshot()
            self.assertTrue(state["active"])
            self.assertEqual(state["step"], 4)
            self.assertEqual(state["total_steps"], 12)
        self.assertFalse(controller.snapshot()["active"])


if __name__ == "__main__":
    unittest.main()
