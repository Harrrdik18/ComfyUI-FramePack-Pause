import importlib
import pathlib
import sys
import tempfile
import threading
import time
import types
import unittest

from pause_controller import CONTROLLER
from patcher import install_import_hook, patch_pipeline_module, patch_sampler_module


class PatcherTests(unittest.TestCase):
    def tearDown(self):
        CONTROLLER.resume()

    def make_sampler_module(self):
        module = types.ModuleType("fake.diffusers_helper.k_diffusion.uni_pc_fm")
        module.FlowMatchUniPC = type("FlowMatchUniPC", (), {})
        module.trange = range
        return module

    def test_wraps_trange(self):
        module = self.make_sampler_module()
        self.assertTrue(patch_sampler_module(module))
        self.assertEqual(list(module.trange(3)), [0, 1, 2])

    def test_pause_blocks_before_next_sampler_iteration(self):
        module = self.make_sampler_module()
        patch_sampler_module(module)
        CONTROLLER.pause()
        done = threading.Event()
        output = []

        def consume():
            output.extend(module.trange(2))
            done.set()

        thread = threading.Thread(target=consume)
        thread.start()
        time.sleep(0.05)
        self.assertFalse(done.is_set())
        CONTROLLER.resume()
        self.assertTrue(done.wait(1))
        thread.join(timeout=1)
        self.assertEqual(output, [0, 1])

    def test_pause_does_not_block_after_final_iteration(self):
        module = self.make_sampler_module()
        patch_sampler_module(module)
        with CONTROLLER.framepack_job(1, 1):
            iterator = iter(module.trange(1))
            self.assertEqual(next(iterator), 0)
            CONTROLLER.pause()
            with self.assertRaises(StopIteration):
                next(iterator)
        self.assertFalse(CONTROLLER.snapshot()["pause_requested"])

    def test_late_import_is_patched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            dirs = [root / "fakefp", root / "fakefp" / "diffusers_helper",
                    root / "fakefp" / "diffusers_helper" / "k_diffusion"]
            for directory in dirs:
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "__init__.py").write_text("", encoding="utf-8")
            (dirs[-1] / "uni_pc_fm.py").write_text(
                "class FlowMatchUniPC: pass\ndef trange(n): return range(n)\n",
                encoding="utf-8",
            )
            sys.path.insert(0, temp_dir)
            try:
                install_import_hook()
                imported = importlib.import_module("fakefp.diffusers_helper.k_diffusion.uni_pc_fm")
                self.assertTrue(getattr(imported.trange, "__framepack_pause_wrapped__", False))
            finally:
                sys.path.remove(temp_dir)
                for name in list(sys.modules):
                    if name == "fakefp" or name.startswith("fakefp."):
                        del sys.modules[name]

    def test_pipeline_scales_callback_over_sections(self):
        module = types.ModuleType("fake.diffusers_helper.pipelines.k_diffusion_hunyuan")

        def sample_hunyuan(callback=None):
            callback(2, "latent", None, 4)
            return "done"

        module.sample_hunyuan = sample_hunyuan
        self.assertTrue(patch_pipeline_module(module))
        received = []
        with CONTROLLER.framepack_job(total_sections=3, steps_per_section=4):
            with CONTROLLER.sampler_loop(4):
                self.assertEqual(
                    module.sample_hunyuan(callback=lambda step, x0, x, total: received.append((step, total))),
                    "done",
                )
                self.assertEqual(received[-1], (2, 12))
                self.assertEqual(CONTROLLER.snapshot()["progress_current"], 3)
            with CONTROLLER.sampler_loop(4):
                module.sample_hunyuan(callback=lambda step, x0, x, total: received.append((step, total)))
                self.assertEqual(received[-1], (6, 12))
                self.assertEqual(CONTROLLER.snapshot()["progress_current"], 7)

    def test_patch_is_idempotent(self):
        module = self.make_sampler_module()
        patch_sampler_module(module)
        wrapped = module.trange
        self.assertTrue(patch_sampler_module(module))
        self.assertIs(module.trange, wrapped)


if __name__ == "__main__":
    unittest.main()
