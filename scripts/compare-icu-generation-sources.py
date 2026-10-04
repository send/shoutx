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

DEPENDENCY_PAIRS = {
    'collationdatareader.cpp': [
        ('int32_t{settings->getMaxVariable()}', 'settings->getMaxVariable()'),
    ],
    'collationdatareader.h': [
        ('CollationDataReader();  // no constructor',
         'CollationDataReader() = delete;  // no constructor'),
    ],
    'collationdata.h': [
        ('    enum {\n'
         '        REORDER_RESERVED_BEFORE_LATIN = UCOL_REORDER_CODE_FIRST + 14,\n'
         '        REORDER_RESERVED_AFTER_LATIN\n'
         '    };',
         '    static constexpr int32_t REORDER_RESERVED_BEFORE_LATIN = UCOL_REORDER_CODE_FIRST + 14;\n'
         '    static constexpr int32_t REORDER_RESERVED_AFTER_LATIN = REORDER_RESERVED_BEFORE_LATIN + 1;'),
        ('    enum {\n'
         '        MAX_NUM_SPECIAL_REORDER_CODES = 8,\n'
         '        /** C++ only, data reader check scriptStartsLength. */\n'
         '        MAX_NUM_SCRIPT_RANGES = 256\n'
         '    };',
         '    static constexpr int32_t MAX_NUM_SPECIAL_REORDER_CODES = 8;\n'
         '    /** C++ only, data reader check scriptStartsLength. */\n'
         '    static constexpr int32_t MAX_NUM_SCRIPT_RANGES = 256;'),
        ('(uint32_t)p[0]', 'static_cast<uint32_t>(p[0])'),
    ],
    'utrie2_impl.h': [],
    'utrie2.h': [],
    'utrie2.cpp': [('return 0;', 'return nullptr;')],
    'ucharstrieiterator.cpp': [
        ('length=(int32_t)((uint32_t)length>>16);',
         'length = static_cast<int32_t>(static_cast<uint32_t>(length) >> 16);'),
        ('UBool isFinal=(UBool)(node>>15);', 'UBool isFinal = static_cast<UBool>(node >> 15);'),
        ('(int32_t)(skipDelta(pos)-uchars_)', 'static_cast<int32_t>(skipDelta(pos) - uchars_)'),
        ('(int32_t)(pos-uchars_)', 'static_cast<int32_t>(pos - uchars_)'),
    ],
    'ucharstrie.cpp': [
        ('UBool isFinal=(UBool)(node>>15);', 'UBool isFinal = static_cast<UBool>(node >> 15);'),
    ],
}


def select_dependency(name, source):
    """Explicit text slices, not C++ parsing; raw hashes always cover full files."""
    if name == 'utrie2.h':
        marker = '#ifdef __cplusplus'
        tail = '/* Internal definitions ----------------------------------------------------- */'
        if source.count(marker) != 1 or source.count(tail) != 1:
            raise ValueError('missing or ambiguous utrie2.h boundaries')
        first, last = source.index(marker), source.index(tail)
        if first >= last:
            raise ValueError('reversed utrie2.h boundaries')
        return source[:first] + source[last:]
    if name == 'utrie2.cpp':
        start = 'U_CAPI UTrie2 * U_EXPORT2\nutrie2_openFromSerialized('
        end = 'U_CAPI UTrie2 * U_EXPORT2\nutrie2_openDummy('
        if source.count(start) != 1 or source.count(end) != 1:
            raise ValueError('missing or ambiguous utrie2 function boundaries')
        first, last = source.index(start), source.index(end)
        if first >= last:
            raise ValueError('reversed utrie2 function boundaries')
        return source[first:last]
    return source


def normalize(name, source, pairs=None):
    for before, after in [('NULL', 'nullptr'), ('TRUE', 'true'),
                          ('FALSE', 'false'), ('UChar', 'char16_t')]:
        source = re.sub(r'\b' + before + r'\b', after, source)
    for before, after in (PAIRS if pairs is None else pairs)[name]:
        source = source.replace(before, after)
    return source


def compare(folder, dependencies=False):
    pairs = DEPENDENCY_PAIRS if dependencies else PAIRS
    for name in pairs:
        normalized = []
        for version in VERSIONS:
            with (folder / f'{name}-{version}').open('rb') as stream:
                raw = stream.read(SOURCE_CAP + 1)
            if len(raw) > SOURCE_CAP:
                raise ValueError('source size cap')
            source = raw.decode('utf-8')
            if dependencies:
                source = select_dependency(name, source)
            source = normalize(name, source, pairs)
            normalized.append(source)
            print(name, version, 'raw', hashlib.sha256(raw).hexdigest(),
                  'normalized', hashlib.sha256(source.encode()).hexdigest())
        print(name, 'normalizedIdentical', len(set(normalized)) == 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--dependencies', action='store_true',
                        help='compare decoder dependencies; utrie2.h/.cpp use explicit slices')
    args = parser.parse_args()
    try:
        compare(args.folder, args.dependencies)
    except (OSError, ValueError) as error:
        parser.exit(1, f'comparison incomplete: {error}\n')
