import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('GROQ_API_KEY', 'test-only')
os.environ.setdefault('PEXELS_API_KEY', 'test-only')
from src import model_audit


class ModelAuditTests(unittest.TestCase):
    def test_received_response_is_retained_before_renderer_mutates_scene_roles(self):
        original = {'scenes': [{'text': 'original generated words'}], 'source_id': '123'}
        sources = [{'id': '123', 'text': 'exact reference input'}]
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                with patch.object(model_audit, 'OUTPUT_DIR', Path(folder) / 'output'), \
                     patch.object(model_audit, 'checkpoint') as publish, \
                     patch.dict(os.environ, {'PUBLISH_UPLOAD_CHECKPOINTS': '1', 'GITHUB_RUN_ID': 'test-only'}):
                    path = model_audit.received(original, sources, 1)
                    original['scenes'].append({'text': 'renderer closing'})
                    model_audit.update(path, 'validation_failed', error='exact rejection')
                    data = json.loads(path.read_text())
                    self.assertEqual(len(data['raw_groq_package']['scenes']), 1)
                    self.assertEqual(data['reference_sources'], sources)
                    self.assertEqual(data['error'], 'exact rejection')
                    self.assertEqual(data['stage'], 'validation_failed')
                    self.assertTrue(all(call.args[0] == [Path('script_progress.json')] for call in publish.call_args_list))
            finally:
                os.chdir(previous)

    def test_no_diagnostic_publication_when_checkpoint_mode_is_off(self):
        with patch.dict(os.environ, {'PUBLISH_UPLOAD_CHECKPOINTS': '0'}), patch.object(model_audit, 'checkpoint') as publish:
            self.assertIsNone(model_audit.received({}, [], 1))
        publish.assert_not_called()
