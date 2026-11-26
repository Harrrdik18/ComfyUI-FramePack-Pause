import sys
import types
import unittest

from node_hook import patch_framepack_class, patch_registered_framepack_nodes
from pause_controller import CONTROLLER


class FramePackNodeHookTests(unittest.TestCase):
    def tearDown(self):
        CONTROLLER.resume()

    def test_wraps_sampler_process_and_calculates_section_total(self):
        class FramePackSampler:
            def process(self, total_second_length, latent_window_size, steps):
                return "ok"

        self.assertTrue(patch_framepack_class(FramePackSampler))
        self.assertEqual(FramePackSampler().process(3.6, 9, 4), "ok")
        state = CONTROLLER.snapshot()
        self.assertEqual(state["total_sections"], 3)
        self.assertEqual(state["progress_total"], 12)
        self.assertEqual(state["phase"], "complete")

    def test_registry_discovery_patches_classes(self):
        class FramePackSingleFrameSampler:
            def process(self, steps=5):
                return "single"

        fake_core_nodes = types.ModuleType("nodes")
        fake_core_nodes.NODE_CLASS_MAPPINGS = {
            "FramePackSingleFrameSampler": FramePackSingleFrameSampler
        }
        old_module = sys.modules.get("nodes")
        sys.modules["nodes"] = fake_core_nodes
        try:
            self.assertIn("FramePackSingleFrameSampler", patch_registered_framepack_nodes())
            self.assertTrue(getattr(
                FramePackSingleFrameSampler.process,
                "__framepack_pause_job_wrapped__",
                False,
            ))
        finally:
            if old_module is None:
                del sys.modules["nodes"]
            else:
                sys.modules["nodes"] = old_module


if __name__ == "__main__":
    unittest.main()
