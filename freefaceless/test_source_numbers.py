import unittest
from src.source_numbers import integer_words, source_spellings


class SourceNumberTests(unittest.TestCase):
    def test_place_values_are_complete_with_natural_turkish_grouping(self):
        values = {0: 'sıfır', 56: 'elli altı', 100: 'yüz', 1000: 'bin',
                  1956: 'bin dokuz yüz elli altı', 1096: 'bin doksan altı',
                  1000000: 'bir milyon', 1230456: 'bir milyon iki yüz otuz bin dört yüz elli altı'}
        for number, words in values.items():
            self.assertEqual(integer_words(number), words)

    def test_guidance_comes_only_from_actual_source_text_and_keeps_ordinals(self):
        rows = source_spellings([{'id': '123456789', 'text': 'Founded in 1956. In the 20th century the value was 1.5 and 1,500.'}])
        self.assertEqual(rows, [{'source_id': '123456789', 'integer_spellings': {
            '1956': 'bin dokuz yüz elli altı', '20th': 'yirminci'}}])
