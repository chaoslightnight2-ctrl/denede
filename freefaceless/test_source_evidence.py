import unittest
from src.script import evidence_source


class SourceEvidenceTests(unittest.TestCase):
    def test_quote_must_belong_to_the_exact_selected_source(self):
        sources = [{'id': 'one', 'text': 'The Moon orbits Earth.'}, {'id': 'two', 'text': 'Earth orbits the Sun.'}]
        self.assertEqual(evidence_source({'source_id': 'one', 'source_fact_quote': 'The Moon orbits Earth.'}, sources), sources[0])
        for data in ({'source_id': 'one', 'source_fact_quote': 'Earth orbits the Sun.'},
                     {'source_id': 'unknown', 'source_fact_quote': 'The Moon orbits Earth.'},
                     {'source_id': 'one', 'source_fact_quote': ''},
                     {'source_id': 'one', 'source_fact_quote': 'The Moon is made of cheese.'}):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'verbatim'):
                evidence_source(data, sources)
