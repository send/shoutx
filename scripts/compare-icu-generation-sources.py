"""Research comparison: exact, disclosed source spelling normalization.

Not a native equivalence verifier. Reads separately acquired official files,
prints hashes and equality only, and neither downloads nor exports source.
"""
import argparse
import hashlib
from pathlib import Path
import re

VERSIONS = ('70-1', '72-1', '74-2', '76-1', '78.1')
SOURCE_CAP = 1024 * 1024
PAIRS = {
    # This intentionally leaves CONTRACT_HAS_STARTER and its comment intact:
    # 70.1 differs from later headers; do not normalize away a new flag.
    'collation.h': [
        (f'({t})({x})', f'static_cast<{t}>({x})') for t, x in [
            ('int64_t', 'ce32 & 0xffffff00'), ('int64_t', 'ce32 & 0xff000000'),
            ('int64_t', 'ce32 & 0xffff0000'), ('int32_t', 'ce32 & 0xf'),
            ('int32_t', 'ce32 >> 13'), ('char', '(ce32 >> 8) & 0xf'),
        ]
    ] + [('(int64_t)ce32', 'static_cast<int64_t>(ce32)'),
         ('(int64_t)p', 'static_cast<int64_t>(p)'),
         ('Collation();  // No instantiation.', 'Collation() = delete;  // No instantiation.')],
    'collationiterator.cpp': [
        ('(uint32_t)prefixes.getValue()', 'static_cast<uint32_t>(prefixes.getValue())'),
        ('(uint32_t)suffixes.getValue()', 'static_cast<uint32_t>(suffixes.getValue())'),
        ('(uint8_t)fcd16', 'static_cast<uint8_t>(fcd16)'),
    ],
    'utf16collationiterator.cpp': [
        (f'({t})({x})', f'static_cast<{t}>({x})') for t, x in [
            ('int32_t', 'pos - start'), ('int32_t', 'pos - rawStart'),
            ('int32_t', 'segmentStart - rawStart'), ('int32_t', 'segmentLimit - rawStart'),
            ('int32_t', 'to - from'), ('uint8_t', 'fcd16 >> 8'),
        ]
    ] + [('(uint8_t)fcd16', 'static_cast<uint8_t>(fcd16)')],
    'coleitr.cpp': [
        ('(uint32_t)(ce >> 32)', 'static_cast<uint32_t>(ce >> 32)'),
        ('(uint32_t)ce', 'static_cast<uint32_t>(ce)'),
        ('(UColAttributeValue)rbc_->settings->getStrength()',
         'static_cast<UColAttributeValue>(rbc_->settings->getStrength())'),
        ('(int32_t)lastHalf', 'static_cast<int32_t>(lastHalf)'),
    ],
    'collationsettings.h': [
        ('(uint32_t)b', 'static_cast<uint32_t>(b)'),
        ('(MaxVariable)((options & MAX_VARIABLE_MASK) >> MAX_VARIABLE_SHIFT)',
         'static_cast<MaxVariable>((options & MAX_VARIABLE_MASK) >> MAX_VARIABLE_SHIFT)'),
    ],
    'ucharstrie.h': [
        ('(uint64_t)(pos_ - uchars_)', 'static_cast<uint64_t>(pos_ - uchars_)'),
        ('UCharsTrie &operator=(const UCharsTrie &other);',
         'UCharsTrie &operator=(const UCharsTrie &other) = delete;'),
        ('(UStringTrieResult)(USTRINGTRIE_INTERMEDIATE_VALUE-(node>>15))',
         'static_cast<UStringTrieResult>(USTRINGTRIE_INTERMEDIATE_VALUE - (node >> 15))'),
    ],
}


def normalize(name, source):
    for before, after in [('NULL', 'nullptr'), ('TRUE', 'true'),
                          ('FALSE', 'false'), ('UChar', 'char16_t')]:
        source = re.sub(r'\b' + before + r'\b', after, source)
    for before, after in PAIRS[name]:
        source = source.replace(before, after)
    return source


def compare(folder):
    for name in PAIRS:
        normalized = []
        for version in VERSIONS:
            with (folder / f'{name}-{version}').open('rb') as stream:
                raw = stream.read(SOURCE_CAP + 1)
            if len(raw) > SOURCE_CAP:
                raise ValueError('source size cap')
            source = raw.decode('utf-8')
            source = normalize(name, source)
            normalized.append(source)
            print(name, version, 'raw', hashlib.sha256(raw).hexdigest(),
                  'normalized', hashlib.sha256(source.encode()).hexdigest())
        print(name, 'normalizedIdentical', len(set(normalized)) == 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    try:
        compare(args.folder)
    except (OSError, ValueError) as error:
        parser.exit(1, f'comparison incomplete: {error}\n')
