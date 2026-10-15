from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('publication_audit', Path(__file__).resolve().parents[1] / 'maintenance/inspect_channel_publication.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PublicationStatusTests(unittest.TestCase):
    def test_processed_private_upload_is_not_a_publication(self):
        now = datetime(2026, 10, 15, 17, tzinfo=timezone.utc)
        video = {'status': {'uploadStatus': 'processed', 'privacyStatus': 'private'}}
        self.assertEqual(audit.publication_state(video, now), 'private_unscheduled')
        video['status']['publishAt'] = '2026-10-15T18:00:00Z'
        self.assertEqual(audit.publication_state(video, now), 'scheduled_wait')
        video['status']['publishAt'] = '2026-10-15T16:00:00Z'
        self.assertEqual(audit.publication_state(video, now), 'overdue_not_public')
        video['status']['privacyStatus'] = 'public'
        self.assertEqual(audit.publication_state(video, now), 'public')

    def test_failed_processing_overrides_an_accepted_insert(self):
        self.assertEqual(audit.publication_state({'status': {'uploadStatus': 'uploaded', 'privacyStatus': 'private'},
                         'processingDetails': {'processingStatus': 'failed'}}, datetime.now(timezone.utc)), 'youtube_failed')
