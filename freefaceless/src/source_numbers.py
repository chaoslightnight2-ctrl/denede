"""Exact integer spellings derived from real source text, never ready narration."""
import re

ONES = ('sıfır', 'bir', 'iki', 'üç', 'dört', 'beş', 'altı', 'yedi', 'sekiz', 'dokuz')
TENS = ('', 'on', 'yirmi', 'otuz', 'kırk', 'elli', 'altmış', 'yetmiş', 'seksen', 'doksan')
ORDINAL = {'sıfır': 'sıfırıncı', 'bir': 'birinci', 'iki': 'ikinci', 'üç': 'üçüncü',
           'dört': 'dördüncü', 'beş': 'beşinci', 'altı': 'altıncı', 'yedi': 'yedinci',
           'sekiz': 'sekizinci', 'dokuz': 'dokuzuncu', 'on': 'onuncu', 'yirmi': 'yirminci',
           'otuz': 'otuzuncu', 'kırk': 'kırkıncı', 'elli': 'ellinci', 'altmış': 'altmışıncı',
           'yetmiş': 'yetmişinci', 'seksen': 'sekseninci', 'doksan': 'doksanıncı',
           'yüz': 'yüzüncü', 'bin': 'bininci', 'milyon': 'milyonuncu',
           'milyar': 'milyarıncı', 'trilyon': 'trilyonuncu'}


def integer_words(value):
    value = int(value)
    if abs(value) >= 10 ** 15:
        raise ValueError('Integer spelling range exceeded')
    if value < 0:
        return 'eksi ' + integer_words(-value)
    if value == 0:
        return ONES[0]
    words = []
    for amount, name in ((10 ** 12, 'trilyon'), (10 ** 9, 'milyar'), (10 ** 6, 'milyon'), (1000, 'bin')):
        count, value = divmod(value, amount)
        if count:
            if amount != 1000 or count != 1:
                words.append(integer_words(count))
            words.append(name)
    hundreds, value = divmod(value, 100)
    if hundreds:
        if hundreds != 1:
            words.append(ONES[hundreds])
        words.append('yüz')
    tens, ones = divmod(value, 10)
    if tens:
        words.append(TENS[tens])
    if ones:
        words.append(ONES[ones])
    return ' '.join(words)


def source_spellings(sources):
    rows = []
    for source in sources:
        text = source['text']
        values = {}
        for match in re.finditer(r'(?<![A-Za-z0-9_])([+-]?\d{1,14})(st|nd|rd|th|s)?(?![A-Za-z0-9_])', text):
            start, end = match.span()
            # Do not turn a decimal or comma-grouped value into separate integers.
            if ((start >= 2 and text[start - 1] in '.,' and text[start - 2].isdigit()) or
                (end + 1 < len(text) and text[end] in '.,' and text[end + 1].isdigit())):
                continue
            spoken = integer_words(match.group(1))
            suffix = match.group(2)
            if suffix == 's':
                # A decade or abbreviated unit needs contextual inflection;
                # do not present it as an unqualified integer spelling.
                continue
            if suffix in ('st', 'nd', 'rd', 'th'):
                parts = spoken.split()
                parts[-1] = ORDINAL[parts[-1]]
                spoken = ' '.join(parts)
            values[match.group(0)] = spoken
        if values:
            rows.append({'source_id': source['id'], 'integer_spellings': values})
    return rows
