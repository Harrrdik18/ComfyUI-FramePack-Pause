import importlib
import pathlib
import sys
import tempfile
import threading
import time
import types
import unittest

from pause_controller import CONTROLLER
from patcher import install_import_hook, patch_sampler_module


class PatcherTests(unittest.TestCase):
    def tearDown(self):
        CONTROLLER.resume()

    def test_wraps_trange(self):
        module = types.ModuleType("fake.diffusers_helper.k_diffusion.uni_pc_fm")
        module.FlowMatchUniPC = type("FlowMatchUniPC", (), {})
        module.trange = range
        self.assertTrue(patch_sampler_module(module))
        self.assertEqual(list(module.trange(3)), [0, 1, 2])

    def test_pause_waits_at_iterator_boundary(self):
        module = types.ModuleType("fake.diffusers_helper.k_diffusion.uni_pc_fm")
        module.FlowMatchUniPC = type("FlowMatchUniPC", (), {})
        module.trange = range
        patch_sampler_module(module)
        CONTROLLER.pause()
        done = threading.Event()
        output = []

        def consume():
            output.extend(module.trange(1))
            done.set()

        thread = threading.Thread(target=consume)
        thread.start()
        time.sleep(0.05)
        self.assertFalse(done.is_set())
        CONTROLLER.resume()
        self.assertTrue(done.wait(1))
        thread.join(timeout=1)
        self.assertEqual(output, [0])

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

    def test_patch_is_idempotent(self):
        module = types.ModuleType("fake.diffusers_helper.k_diffusion.uni_pc_fm")
        module.FlowMatchUniPC = type("FlowMatchUniPC", (), {})
        module.trange = range
        patch_sampler_module(module)
        wrapped = module.trange
        self.assertTrue(patch_sampler_module(module))
        self.assertIs(module.trange, wrapped)


if __name__ == "__main__":
    unittest.main()
