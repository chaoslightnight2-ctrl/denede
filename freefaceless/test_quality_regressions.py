import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault('GROQ_API_KEY', 'test-only')
os.environ.setdefault('PEXELS_API_KEY', 'test-only')
from src import captions
from src.quality import validate_and_prepare, validate_visual_query
from src.assemble import _scene_durations


class DenedeQualityTests(unittest.TestCase):
    def test_scene_durations_preserve_pauses_and_full_audio_tail(self):
        words = [{'word': 'ilk', 'start': .2, 'end': .5}, {'word': 'sahne', 'start': .6, 'end': 1.0},
                 {'word': 'son', 'start': 2.0, 'end': 2.3}, {'word': 'sahne', 'start': 2.4, 'end': 2.8}]
        durations = _scene_durations(words, [{'text': 'ilk sahne'}, {'text': 'son sahne'}], 3.5)
        self.assertEqual(durations, [2.0, 1.5])
        self.assertEqual(sum(durations), 3.5)
    def test_real_tts_boundaries_required(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                captions.transcribe_words(Path(directory) / 'missing.mp3')

    def test_visual_quotes_are_cleaned_without_transliterating_turkish(self):
        self.assertEqual(validate_visual_query('"ocean waves surface"'), 'ocean waves surface')
        with self.assertRaises(ValueError):
            validate_visual_query('okyanus dalgaları yüzey')

    def test_raw_source_markers_are_checked_before_cleaning(self):
        data = {'scenes': [{'text': 'https://example.com Bu sahne doğrudan seslendirilen dört kelime', 'visual_query': 'ocean waves surface'}] * 5}
        with self.assertRaisesRegex(ValueError, 'Ham sahne'):
            validate_and_prepare(data)


if __name__ == '__main__':
    unittest.main()
