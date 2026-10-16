import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from requests import HTTPError
from unittest.mock import patch
from src import daily_batch
from src.groq_client import GroqQuotaError
from src.groq_budget import GroqBudgetError


class ProviderStopTests(unittest.TestCase):
    def test_provider_stop_preserves_receipt_and_does_not_try_next_niche(self):
        for error in (GroqQuotaError('quota exhausted'), GroqBudgetError('request budget exhausted'), HTTPError('HTTP 503 retries exhausted')):
            with self.subTest(error=error), TemporaryDirectory() as folder:
                manifest = Path(folder) / 'manifest.json'
                with patch.object(daily_batch, 'MANIFEST', manifest), patch('sys.argv', ['daily_batch']), \
                     patch('src.upload_recovery.requested', return_value=False), \
                     patch.dict(os.environ, {'DAILY_VIDEO_COUNT': '3', 'PUBLISH_UPLOAD_CHECKPOINTS': '0'}), \
                     patch.object(daily_batch.state, 'load', return_value={'published': []}), \
                     patch.object(daily_batch.pipeline, 'run_once', side_effect=[
                         {'topic': 'first', 'video_id': 'accepted-id', 'upload_status': 'api_insert_confirmed'}, error]) as run:
                    with self.assertRaises(type(error)):
                        daily_batch.main()
                rows = json.loads(manifest.read_text(encoding='utf-8'))
                self.assertEqual(run.call_count, 2)
                self.assertEqual(rows[0]['video_id'], 'accepted-id')
                self.assertFalse(rows[1]['ok'])
