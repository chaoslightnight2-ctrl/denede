import os
import unittest
from unittest.mock import patch

with patch.dict(os.environ, {'GROQ_API_KEY': 'unit-test-only', 'PEXELS_API_KEY': 'unit-test-only'}):
    from src.script import repair_sources


class RepeatedTopicRepairTests(unittest.TestCase):
    def test_used_topic_does_not_pin_all_repairs_to_its_old_source(self):
        sources = [{'id': 'old', 'text': 'actual old source'}, {'id': 'fresh', 'text': 'actual fresh source'}]
        self.assertEqual(repair_sources(sources, {'source_id': 'old'}, ValueError('Konu tekrar ediyor; başka olgu seç')), sources[1:])
        self.assertEqual(sources[0]['text'], 'actual old source')

    def test_format_repair_keeps_its_actual_source_and_never_invents_a_reference(self):
        source = {'id': 'only', 'text': 'actual reference'}
        self.assertEqual(repair_sources([source], {'source_id': 'only'}, ValueError('Başlık uzun')), [source])
        self.assertEqual(repair_sources([source], {'source_id': 'only'}, ValueError('Konu tekrar ediyor')), [source])
