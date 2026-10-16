import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from src import script, pipeline

class PromptFirstFactTests(unittest.TestCase):
    def package(self):
        return {'source_id': 'one', 'topic': 'Ay', 'title': 'Ayın Dünya çevresindeki yolculuğu',
                'description': 'Ay Dünya çevresinde dolanır', 'tags': ['ay', 'dünya', 'uzay', 'yörünge', 'uydu'],
                'hashtags': {'primary': 'Ay', 'secondary': 'uzay'},
                'scenes': [{'text': 'Ay Dünya çevresinde dolanır', 'visual_query': 'moon earth orbit'}],
                'closing_question': 'Sen Ayı izler misin', 'closing_visual_query': 'moon night sky',
                'cta': 'İlginç Gerçekler kanalına abone ol'}

    def test_response_is_prepared_without_editorial_rejection_or_proof(self):
        sources = [{'id': 'one', 'title': 'Moon', 'text': 'The Moon orbits Earth.'}]
        with patch.object(script, 'fetch_sources', return_value=sources), \
             patch.object(script.state, 'load', return_value={'used_topics': []}), \
             patch.object(script.validated_draft, 'load', return_value=None), \
             patch.object(script, 'chat_json', return_value=copy.deepcopy(self.package())) as request:
            data = script.generate()
        request.assert_called_once()
        self.assertEqual(data['reference_source'], sources[0])
        self.assertEqual(data['spoken_text'].count('abone ol'), 1)
        self.assertNotIn('publication_approval', data)
        self.assertNotIn('editorial_review', data)

    def test_duration_never_requests_new_prose_or_clears_saved_draft(self):
        for duration in (12, 22, 38):
            with self.subTest(duration=duration), TemporaryDirectory() as folder, \
                 patch.object(pipeline, 'OUTPUT_DIR', Path(folder)), \
                 patch.object(script, 'generate', return_value={'topic': 'Ay', 'tts_text': 'Ay döner.', 'full_text': 'Ay döner'}) as request, \
                 patch.object(pipeline.voice, 'synth', return_value=Path('voice.mp3')), \
                 patch.object(pipeline.captions, 'transcribe_words', return_value=[{'word': 'Ay', 'end': duration}]):
                self.assertEqual(pipeline._pick_script(None)[-1], duration)
            request.assert_called_once()
