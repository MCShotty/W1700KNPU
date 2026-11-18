"""Streaming inventory controls against the unchanged frozen world launcher."""
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import npu_world_stream_host as host


class StreamedWorldTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.tree = self.root / "tree"
        self.tree.mkdir()

    def test_same_fields_as_frozen_tree_state(self):
        (self.tree / "z").mkdir()
        (self.tree / "z/data").write_bytes(b"old\0")
        (self.tree / "empty").mkdir()
        (self.tree / "literal").symlink_to("z/../z")
        (self.tree / "z/data").chmod(0o751)
        out = BytesIO()
        actual = host.inventory(self.tree, out)
        rows = dict(json.loads(line) for line in out.getvalue().splitlines())
        self.assertEqual(rows, host.frozen_world.tree_state(self.tree))
        self.assertEqual(actual["entries"], len(rows))
        self.assertEqual(actual["sha256"], sha256(out.getvalue()).hexdigest())
        self.assertEqual(host.inventory(self.tree), actual)
        self.assertNotIn("literal/data", rows)

    def test_detects_changes_in_content_metadata_and_literal_link(self):
        a, b = self.tree / "data", self.tree / "link"
        a.write_bytes(b"a")
        b.symlink_to("data")
        prior = host.inventory(self.tree)
        for change in (lambda: a.write_bytes(b"b"), lambda: a.chmod(0o700),
                       lambda: (b.unlink(), b.symlink_to("./data")), a.unlink):
            with self.subTest(change=change):
                change()
                after = host.inventory(self.tree)
                self.assertNotEqual(after, prior)
                prior = after

    def test_traversal_order_is_stable(self):
        for node in ("z", "a"):
            (self.tree / node).mkdir()
            (self.tree / node / "file").touch()
        real_walk = os.walk

        def reverse_walk(*args, **kwargs):
            for base, dirs, files in real_walk(*args, **kwargs):
                dirs.reverse()
                files.reverse()
                yield base, dirs, files

        want = host.inventory(self.tree)
        with patch.object(host.os, "walk", side_effect=reverse_walk):
            self.assertEqual(host.inventory(self.tree), want)

    def test_refuses_special_nodes_and_walk_errors(self):
        fifo = self.tree / "not-a-file"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(AssertionError, "special-build-input"):
            host.inventory(self.tree)
        fifo.unlink()

        def denied(*args, onerror, **kwargs):
            onerror(PermissionError("synthetic denied directory"))

        with patch.object(host.os, "walk", side_effect=denied), self.assertRaises(PermissionError):
            host.inventory(self.tree)

    def test_terminal_gate_precedes_namespace_and_output_creation(self):
        world = host.frozen_world
        capsule = self.root / "receipt.json"
        capsule.write_bytes(b"synthetic capsule")
        producer = self.root / "producer.json"
        producer.write_bytes(b"synthetic producer")
        output = self.root / "output"
        args = SimpleNamespace(name="fixture", snapshot=capsule, snapshot_sha256=host.digest(capsule),
                               module_receipt=producer, producer_sha256=host.digest(producer),
                               start=self.root / "start.json", start_sha256="f" * 64,
                               terminal=self.root / "terminal.json", terminal_sha256="e" * 64)
        sources = {"files": {"producer.json": args.producer_sha256}}
        with patch.object(world, "ROOT", self.root), patch.object(host.os, "getuid", return_value=1000), \
                patch.object(world, "output_root", return_value=output), \
                patch.object(world, "snapshot", return_value=(self.root, sources)), \
                patch.object(host, "verify_replay", side_effect=ValueError("no terminal pass")), \
                patch.object(world, "command") as spawn:
            with self.assertRaisesRegex(ValueError, "no terminal pass"):
                host.run(args)
            spawn.assert_not_called()
            self.assertFalse(output.exists())

    def test_world_success_still_requires_unchanged_originals(self):
        world = host.frozen_world
        frozen = self.root / "frozen"
        (frozen / "firmware").mkdir(parents=True)
        (frozen / "firmware/source-lock.json").write_text(json.dumps(
            {"kernel": "6.18.52", "openwrt": {"changed_files": []}}))
        lock = host.digest(frozen / "firmware/source-lock.json")
        capsule = self.root / "receipt.json"
        capsule.write_bytes(b"synthetic capsule")
        producer = self.root / "producer.json"
        (frozen / producer.name).write_bytes(b"synthetic producer")
        pin = host.digest(frozen / producer.name)
        sources = {"files": {"producer.json": pin, "tools/npu_isolated_world.py": "c" * 64},
                   "source_commit": "d" * 40}
        output = self.root / "output"
        cache = self.root / "cache"
        cache.mkdir()
        bubblewrap = self.root / "bwrap"
        bubblewrap.touch()
        command = ["exact mocked frozen inner"]
        lower_file = self.tree / "file"
        lower_file.write_bytes(b"protected")

        def exercise(name, mutate):
            args = SimpleNamespace(name=name, snapshot=capsule, snapshot_sha256=host.digest(capsule),
                                   module_receipt=producer, producer_sha256=pin, start=None, start_sha256=None,
                                   terminal=None, terminal_sha256=None)

            def run_child(argv, logfile):
                self.assertEqual(argv, command)
                if mutate:
                    lower_file.write_bytes(b"different")
                base = logfile.parent / "build-upper"
                image = base / "bin/fixture.itb"
                image.parent.mkdir()
                image.write_bytes(b"synthetic image")
                status = base / ("bin/isolated-world-" + name)
                status.mkdir()
                (status / "result.json").write_text(json.dumps(dict(
                    passed=True, world_build=True, image_verification={
                        "image": "tree/bin/fixture.itb", "sha256": host.digest(image),
                    })))
                return dict(returncode=0, host_timeout=False)

            with ExitStack() as stack:
                for attr, value in dict(ROOT=self.root, BUILD=self.tree, CACHE=cache).items():
                    stack.enter_context(patch.object(world, attr, value))
                for attr, value in dict(output_root=output, snapshot=(frozen, sources),
                        namespaces={"mnt": "synthetic"}, identity=[1, 2], linker_input={},
                        download_cache_input={}, producer_context=None, command=command,
                        bubblewrap_input=(bubblewrap, {"sha256": host.digest(bubblewrap)})).items():
                    stack.enter_context(patch.object(world, attr, return_value=value))
                stack.enter_context(patch.object(world, "run_logged", side_effect=run_child))
                stack.enter_context(patch.object(host.os, "getuid", return_value=1000))
                stack.enter_context(patch.object(host, "verify_replay", return_value={
                    "source_lock_sha256": lock, "invocation": "synthetic",
                }))
                stack.enter_context(patch("builtins.print"))
                if mutate:
                    with self.assertRaisesRegex(AssertionError, "isolated-world-unqualified"):
                        host.run(args)
                else:
                    host.run(args)
            report = json.loads((output / name / "result.json").read_bytes())
            self.assertEqual(report["passed"], not mutate)
            self.assertEqual(report["original_build_content_modes_ownership_links_unchanged"], not mutate)
            self.assertEqual(report["envelope"]["command"], command)
            self.assertEqual("physical_image" in report, not mutate)
            self.assertEqual(report["original_inventory_entries"], 2)

        exercise("matches", False)
        exercise("drift", True)


if __name__ == "__main__":
    unittest.main()
