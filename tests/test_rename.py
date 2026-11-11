import os
import shutil
import tempfile
import unittest
from pathlib import Path
from core.audio_processor import AudioProcessor


class TestRename(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.processor = AudioProcessor(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_safe_rename_same_name(self):
        # Create a file "Artist - Title.mp3"
        filename = "Artist - Title.mp3"
        filepath = os.path.join(self.test_dir, filename)
        Path(filepath).touch()

        # Try to rename it to the same name (simulating tag extraction)
        # _safe_rename expects absolute path for old_name if recursive, or relative if not?
        # The fix handles both. Let's pass absolute path as get_audio_files does.

        new_name, changed, error = self.processor._safe_rename(filepath, filename)

        self.assertIsNone(error)
        self.assertFalse(changed)
        self.assertEqual(os.path.basename(new_name), filename)
        self.assertTrue(os.path.exists(filepath))
        self.assertFalse(
            os.path.exists(os.path.join(self.test_dir, "Artist - Title (1).mp3"))
        )

    def test_safe_rename_sanitization_match(self):
        for platform, filename in (
            ("Windows", "ACDC - TNT.mp3"),
            ("Linux", "AC-DC - TNT.mp3"),
            ("Darwin", "AC-DC - TNT.mp3"),
        ):
            with self.subTest(platform=platform):
                directory = Path(self.test_dir) / platform
                directory.mkdir()
                filepath = directory / filename
                filepath.write_bytes(b"unchanged audio")
                self.processor.os_type = platform
                new_name, changed, error = self.processor._safe_rename(
                    str(filepath), "AC/DC - TNT.mp3"
                )
                self.assertIsNone(error)
                self.assertFalse(changed)
                self.assertEqual(Path(new_name), filepath)
                self.assertEqual(filepath.read_bytes(), b"unchanged audio")
                self.assertEqual(list(directory.iterdir()), [filepath])

    def test_safe_rename_recursive_directory(self):
        # Setup a subdirectory
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir)
        filename = "Song.mp3"
        filepath = os.path.join(subdir, filename)
        Path(filepath).touch()

        # Rename "Song.mp3" to "Renamed.mp3"
        # old_name passed as absolute path
        new_name, changed, error = self.processor._safe_rename(filepath, "Renamed.mp3")

        self.assertIsNone(error)
        self.assertTrue(changed)
        self.assertEqual(os.path.basename(new_name), "Renamed.mp3")
        # Check it stayed in subdir
        self.assertTrue(os.path.exists(os.path.join(subdir, "Renamed.mp3")))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "Renamed.mp3")))

    def test_safe_rename_collision(self):
        # File 1: "Song.mp3"
        # File 2: "Song (1).mp3" (already exists)
        # We want to rename "Other.mp3" to "Song.mp3"

        path1 = os.path.join(self.test_dir, "Song.mp3")
        path2 = os.path.join(self.test_dir, "Song (1).mp3")
        path3 = os.path.join(self.test_dir, "Other.mp3")

        # Create files with different content to avoid "identical file" detection
        with open(path1, "w") as f:
            f.write("content1")
        with open(path2, "w") as f:
            f.write("content2")
        with open(path3, "w") as f:
            f.write("content3")

        new_name, changed, error = self.processor._safe_rename(path3, "Song.mp3")

        self.assertIsNone(error)
        self.assertTrue(changed)
        self.assertEqual(os.path.basename(new_name), "Song (2).mp3")
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "Song (2).mp3")))


if __name__ == "__main__":
    unittest.main()
