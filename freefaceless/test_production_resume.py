import json
import os
import types
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
os.environ.setdefault('GROQ_API_KEY', 'test-only')
os.environ.setdefault('PEXELS_API_KEY', 'test-only')
from src import daily_batch, validated_draft

TZ = timezone(timedelta(hours=3))


class ProductionResumeTests(unittest.TestCase):
    def test_partial_day_only_fills_the_remaining_publication_slot(self):
        now = datetime(2026, 10, 15, 10, tzinfo=TZ)
        state = {'published': [{'video_id': f'old-{h}', 'publish_at': now.replace(hour=h).isoformat()} for h in (19, 21)]}
        with TemporaryDirectory() as folder, patch.object(daily_batch, 'MANIFEST', Path(folder) / 'manifest.json'), \
             patch('sys.argv', ['batch']), patch('src.upload_recovery.requested', return_value=False), \
             patch.dict(os.environ, {'DAILY_VIDEO_COUNT': '3', 'PUBLISH_UPLOAD_CHECKPOINTS': '0'}), \
             patch.object(daily_batch, 'datetime', types.SimpleNamespace(now=lambda tz: now)), \
             patch.object(daily_batch.state, 'load', return_value=state), \
             patch.object(daily_batch.pipeline, 'run_once', side_effect=lambda **kw: {
                 'topic': 'new', 'video_id': 'new-id', 'upload_status': 'api_insert_confirmed', 'publish_at': kw['publish_at']}) as run:
            daily_batch.main()
        self.assertEqual(run.call_count, 1)
        at = datetime.fromisoformat(run.call_args.kwargs['publish_at'].replace('Z', '+00:00')).astimezone(TZ)
        self.assertEqual(at, now.replace(hour=23))

    def test_complete_day_makes_no_generation_call(self):
        now = datetime(2026, 10, 15, 10, tzinfo=TZ)
        state = {'published': [{'video_id': f'old-{h}', 'publish_at': now.replace(hour=h).isoformat()} for h in (19, 21, 23)]}
        with patch('sys.argv', ['batch']), patch('src.upload_recovery.requested', return_value=False), \
             patch.dict(os.environ, {'DAILY_VIDEO_COUNT': '3', 'PUBLISH_UPLOAD_CHECKPOINTS': '0'}), \
             patch.object(daily_batch, 'datetime', types.SimpleNamespace(now=lambda tz: now)), \
             patch.object(daily_batch.state, 'load', return_value=state), \
             patch.object(daily_batch.pipeline, 'run_once') as run:
            daily_batch.main()
        run.assert_not_called()

    def test_saved_draft_requires_unchanged_source_and_unused_topic(self):
        source = {'id': 'real-source', 'text': 'actual source body'}
        data = approved_fixture(source)
        with TemporaryDirectory() as folder, patch.object(validated_draft, 'PATH', Path(folder) / 'draft.json'), \
             patch.dict(os.environ, {'PUBLISH_UPLOAD_CHECKPOINTS': '1'}), patch.object(validated_draft, 'checkpoint'):
            validated_draft.save('science', data)
            self.assertEqual(validated_draft.load('science', [source], []), data)
            self.assertIsNone(validated_draft.load('science', [dict(source, text='updated source')], []))
            self.assertIsNone(validated_draft.load('science', [source], ['actual topic']))

    def test_cleared_draft_is_not_reused(self):
        source = {'id': 'real-source', 'text': 'actual source body'}
        data = approved_fixture(source)
        with TemporaryDirectory() as folder, patch.object(validated_draft, 'PATH', Path(folder) / 'draft.json'), \
             patch.dict(os.environ, {'PUBLISH_UPLOAD_CHECKPOINTS': '1'}), patch.object(validated_draft, 'checkpoint'):
            validated_draft.save('science', data)
            validated_draft.clear()
            self.assertIsNone(validated_draft.load('science', [source], []))


if __name__ == '__main__':
    unittest.main()


def approved_fixture(source):
    return {'topic': 'actual topic', 'reference_source': source, 'generation_mode': 'prompt_first_v1'}
