import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault('GROQ_API_KEY', 'test-only')
os.environ.setdefault('PEXELS_API_KEY', 'test-only')
from src import captions
from src.quality import validate_and_prepare, validate_visual_query
from src.assemble import _scene_durations


class DenedeQualityTests(unittest.TestCase):
    def test_rejected_youtube_video_is_never_reported_as_success(self):
        from src import pipeline
        data = {'topic': 'deney', 'title': 'deney', 'description': 'deney', 'tags': [], 'scenes': [], 'spoken_text': 'temiz metin'}
        saved = {'used_topics': [], 'published': [{'video_id': 'AbcDef_1234'}]}
        work = Path('20260930_060000_deney')
        with patch.object(pipeline, '_pick_script', return_value=(data, work, Path('voice.mp3'), [], 32)), \
             patch.object(pipeline.visuals, 'fetch_for_scenes', return_value=[]), \
             patch.object(pipeline.captions, 'write_ass', return_value=Path('captions.ass')), \
             patch.object(pipeline.assemble, 'build', return_value=Path('final.mp4')), \
             patch.object(pipeline, 'validate_rendered_video'), \
             patch.object(pipeline.upload, 'upload_video', return_value='AbcDef_1234'), \
             patch.object(pipeline.upload, 'get_service'), \
             patch.object(pipeline.state, 'add_topic'), patch.object(pipeline.state, 'add_published'), \
             patch.object(pipeline.state, 'load', return_value=saved), patch.object(pipeline.state, 'save'), \
             patch('src.youtube_receipt.confirm', side_effect=ValueError('YouTube rejected video')):
            result = pipeline.run_once()
        self.assertEqual(result['upload_status'], 'youtube_rejected')
        self.assertEqual(saved['published'][0]['upload_status'], 'youtube_rejected')

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
