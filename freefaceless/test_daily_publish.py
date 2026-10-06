import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch
os.environ.setdefault('GROQ_API_KEY', 'test-only')
os.environ.setdefault('PEXELS_API_KEY', 'test-only')
from src import daily_batch, pipeline

TZ = timezone(timedelta(hours=3))


class DailyPublishingTests(unittest.TestCase):
    def test_voice_failure_keeps_exact_source_and_original_groq_response(self):
        package = {'topic': 'audit', 'tts_text': 'test speech',
                   'reference_source': {'id': 'source-id', 'text': 'exact source input'},
                   'raw_groq_package': {'scenes': [{'text': 'original response'}]}}
        with TemporaryDirectory() as folder, patch.object(pipeline, 'OUTPUT_DIR', Path(folder)), \
             patch.object(pipeline.script, 'generate', return_value=package), \
             patch.object(pipeline.voice, 'synth', side_effect=RuntimeError('voice failure')):
            with self.assertRaisesRegex(RuntimeError, 'voice failure'):
                pipeline._pick_script(None)
            files = list(Path(folder).glob('*/script.json'))
            self.assertEqual(len(files), 1)
            saved = json.loads(files[0].read_text(encoding='utf-8'))
            self.assertEqual(saved, package)

    def test_three_default_videos_use_eight_hour_publication_slots(self):
        fixed = datetime(2026, 10, 6, 6, tzinfo=TZ)
        calls = []
        def run(**kwargs):
            calls.append(kwargs)
            return {'topic': str(len(calls)), 'video_id': f'video-{len(calls)}', 'upload_status': 'api_insert_confirmed', 'publish_at': kwargs['publish_at']}
        with TemporaryDirectory() as folder, patch.object(daily_batch, 'MANIFEST', Path(folder) / 'manifest.json'), \
             patch('sys.argv', ['daily_batch']), patch.dict(os.environ, {'DAILY_VIDEO_COUNT': '3', 'PUBLISH_UPLOAD_CHECKPOINTS': '0'}), \
             patch.object(daily_batch, 'datetime', types.SimpleNamespace(now=lambda tz: fixed)), \
             patch.object(daily_batch.state, 'load', return_value={'published': []}), \
             patch.object(daily_batch.pipeline, 'run_once', side_effect=run):
            daily_batch.main()
        self.assertEqual(len(calls), 3)
        times = [datetime.fromisoformat(row['publish_at'].replace('Z', '+00:00')).astimezone(TZ) for row in calls]
        self.assertEqual([at.hour for at in times], [8, 16, 0])
        self.assertEqual(times[1] - times[0], timedelta(hours=8))
        self.assertEqual(times[2] - times[1], timedelta(hours=8))

    def test_new_manifest_does_not_claim_old_receipts_after_failure(self):
        fixed = datetime(2026, 10, 6, 6, tzinfo=TZ)
        with TemporaryDirectory() as folder:
            manifest = Path(folder) / 'manifest.json'
            manifest.write_text(json.dumps([{'video_id': 'old-video', 'ok': True}]))
            first = [True]
            def fail(**kwargs):
                if first[0]:
                    self.assertEqual(json.loads(manifest.read_text()), [])
                    first[0] = False
                raise RuntimeError('Groq unavailable')
            with patch.object(daily_batch, 'MANIFEST', manifest), patch('sys.argv', ['daily_batch']), \
                 patch.dict(os.environ, {'DAILY_VIDEO_COUNT': '3', 'PUBLISH_UPLOAD_CHECKPOINTS': '0'}), \
                 patch.object(daily_batch, 'datetime', types.SimpleNamespace(now=lambda tz: fixed)), \
                 patch.object(daily_batch.state, 'load', return_value={'published': []}), \
                 patch.object(daily_batch.pipeline, 'run_once', side_effect=fail), self.assertRaises(SystemExit):
                daily_batch.main()
            self.assertEqual(len(json.loads(manifest.read_text())), 3)
            self.assertTrue(all(not row.get('video_id') for row in json.loads(manifest.read_text())))

    def test_pipeline_refreshes_stale_schedule_before_insert(self):
        fixed = datetime(2026, 10, 6, 9, 5, tzinfo=TZ)
        data = {'topic': 'deney', 'title': 'deney', 'description': 'deney', 'tags': [], 'scenes': [], 'spoken_text': 'temiz metin'}
        saved = {'used_topics': [], 'published': []}
        with patch.dict(os.environ, {'DAILY_VIDEO_COUNT': '3', 'PUBLISH_UPLOAD_CHECKPOINTS': '0'}), \
             patch.object(pipeline, 'datetime', types.SimpleNamespace(now=lambda tz: fixed, fromisoformat=datetime.fromisoformat)), \
             patch.object(pipeline, '_pick_script', return_value=(data, Path('20261006_060000_deney'), Path('voice.mp3'), [], 32)), \
             patch.object(pipeline.visuals, 'fetch_for_scenes', return_value=[]), \
             patch.object(pipeline.captions, 'write_ass', return_value=Path('captions.ass')), \
             patch.object(pipeline.assemble, 'build', return_value=Path('final.mp4')), \
             patch.object(pipeline, 'validate_rendered_video'), \
             patch.object(pipeline.upload, 'upload_video', return_value='AbcDef_1234') as upload, \
             patch.object(pipeline.upload, 'get_service'), patch.object(pipeline.state, 'add_topic'), \
             patch.object(pipeline.state, 'add_published'), patch.object(pipeline.state, 'load', return_value=saved), \
             patch.object(pipeline.state, 'save'), patch('src.youtube_receipt.confirm', return_value={'upload_status': 'api_insert_confirmed'}):
            result = pipeline.run_once(publish_at='2026-10-06T05:00:00Z')
        self.assertEqual(upload.call_args.kwargs['publish_at'], '2026-10-06T13:00:00Z')
        self.assertEqual(result['publish_at'], '2026-10-06T13:00:00Z')


if __name__ == '__main__':
    unittest.main()
