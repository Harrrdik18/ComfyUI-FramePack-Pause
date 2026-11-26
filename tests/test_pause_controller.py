import threading
import time
import unittest

from pause_controller import PauseController


class PauseControllerTests(unittest.TestCase):
    def test_starts_running(self):
        self.assertFalse(PauseController().snapshot()["paused"])

    def test_pause_blocks_until_resume(self):
        controller = PauseController(poll_interval=0.01)
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
        time.sleep(0.04)
        self.assertFalse(finished.is_set())
        controller.resume()
        self.assertTrue(finished.wait(1))
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())

    def test_sampler_loop_status(self):
        controller = PauseController()
        with controller.sampler_loop(12):
            controller.set_step(4, 12)
            state = controller.snapshot()
            self.assertTrue(state["active"])
            self.assertEqual(state["step"], 4)
            self.assertEqual(state["total_steps"], 12)
        self.assertFalse(controller.snapshot()["active"])

    def test_aggregate_progress_across_sections(self):
        controller = PauseController()
        with controller.framepack_job(total_sections=3, steps_per_section=4):
            with controller.sampler_loop(4):
                controller.set_step(2, 4)
                state = controller.snapshot()
                self.assertEqual(state["section"], 1)
                self.assertEqual(state["progress_current"], 2)
                self.assertEqual(state["progress_total"], 12)
                self.assertAlmostEqual(state["progress_percent"], 16.7, places=1)

            with controller.sampler_loop(4):
                controller.set_step(2, 4)
                state = controller.snapshot()
                self.assertEqual(state["section"], 2)
                self.assertEqual(state["progress_current"], 6)
                self.assertEqual(state["progress_percent"], 50.0)

        state = controller.snapshot()
        self.assertEqual(state["phase"], "complete")
        self.assertEqual(state["progress_percent"], 100.0)
        self.assertFalse(state["active"])

    def test_comfy_interrupt_breaks_pause_wait(self):
        controller = PauseController(poll_interval=0.01)
        controller.pause()

        def interrupt():
            raise RuntimeError("ComfyUI interrupted")

        with self.assertRaisesRegex(RuntimeError, "ComfyUI interrupted"):
            controller.wait_if_paused(check_interrupted=interrupt)
        self.assertEqual(controller.snapshot()["waiting_loops"], 0)

    def test_failed_job_cleans_pause_and_records_error(self):
        controller = PauseController()
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            with controller.framepack_job(2, 3):
                controller.pause()
                raise RuntimeError("test failure")
        state = controller.snapshot()
        self.assertEqual(state["phase"], "interrupted")
        self.assertIn("test failure", state["last_error"])
        self.assertFalse(state["active"])
        self.assertFalse(state["pause_requested"])


if __name__ == "__main__":
    unittest.main()
