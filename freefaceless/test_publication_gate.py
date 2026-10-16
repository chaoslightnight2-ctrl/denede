from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from src import pipeline
import test_production_resume as fixtures


class FactPublicationGateTests(unittest.TestCase):
    def test_boolean_only_draft_cannot_reach_visuals_or_upload(self):
        data = {'topic': 'unreviewed', 'editorial_review': {'valid': True}}
        with patch.object(pipeline, '_pick_script', return_value=(data, Path('20261016_120000_test'), Path('voice.mp3'), [], 22)), \
             patch.object(pipeline.visuals, 'fetch_for_scenes') as visual, patch.object(pipeline.upload, 'upload_video') as upload:
            with self.assertRaises(ValueError):
                pipeline.run_once()
        visual.assert_not_called()
        upload.assert_not_called()

    def test_render_time_title_change_is_rejected_before_upload(self):
        data = fixtures.approved_fixture({'id': 'source', 'text': 'Actual source content for the test fixture.'})
        data.update(topic='actual topic', title='Actual title', description='Actual description', tags=[], scenes=[], spoken_text='speech', tts_text='speech.')
        from src.script import fact_payload, fact_fields
        from src.source_review import make_proof
        data['publication_approval'] = make_proof(fact_payload(data), fact_fields(data['raw_groq_package']), data['reference_source']['text'], data['editorial_review'])
        def render(**kwargs):
            data['title'] = 'A changed headline'
            return Path('final.mp4')
        with patch.object(pipeline, '_pick_script', return_value=(data, Path('20261016_120000_test'), Path('voice.mp3'), [], 22)), \
             patch.object(pipeline.visuals, 'fetch_for_scenes', return_value=[]), \
             patch.object(pipeline.captions, 'write_ass', return_value=Path('captions.ass')), \
             patch.object(pipeline.assemble, 'build', side_effect=render), patch.object(pipeline, 'validate_rendered_video'), \
             patch.object(pipeline.upload, 'upload_video') as upload:
            with self.assertRaises(ValueError):
                pipeline.run_once()
        upload.assert_not_called()
