import os
import shutil
import tempfile
import unittest
from pathlib import Path
from utils.tools import get_audio_files
from core.audio_processor import AudioProcessor


class TestRecursive(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sub_dir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.sub_dir)

        # Create dummy audio files
        Path(os.path.join(self.test_dir, "test1.mp3")).touch()
        Path(os.path.join(self.sub_dir, "test2.mp3")).touch()
        Path(os.path.join(self.test_dir, "text.txt")).touch()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_get_audio_files_non_recursive(self):
        files = get_audio_files(self.test_dir, recursive=False)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith("test1.mp3"))
        self.assertTrue(os.path.isabs(files[0]))

    def test_get_audio_files_recursive(self):
        files = get_audio_files(self.test_dir, recursive=True)
        self.assertEqual(len(files), 2)
        filenames = [os.path.basename(f) for f in files]
        self.assertIn("test1.mp3", filenames)
        self.assertIn("test2.mp3", filenames)
        for f in files:
            self.assertTrue(os.path.isabs(f))

    def test_audio_processor_recursive(self):
        processor = AudioProcessor(self.test_dir, recursive=True)
        self.assertTrue(processor.recursive)
        # We can't easily test process_files without mocking, but we can check if it crashes
        # process_files calls get_audio_files internally


if __name__ == "__main__":
    unittest.main()
