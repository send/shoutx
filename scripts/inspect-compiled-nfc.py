"""Locate five compiled NFC arrays in a hash-identified, bounded binary region.

Offline acquisition aid, not a C++ parser, native-use verifier or NFC decoder.
Prints bounded metadata only. Expected hashes must come from independent evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct

SOURCE_CAP = 4 * 1024 * 1024
BINARY_CAP = 4 * 1024 * 1024 * 1024
REGION_CAP = 64 * 1024 * 1024
ELEMENT_CAP = 65536
CHUNK_SIZE = 1024 * 1024
MATCH_CAP = 1000000
ARRAY_TYPES = {'indexes': ('int32_t', 'i'), 'trieIndex': ('uint16_t', 'H'),
               'trieData': ('uint16_t', 'H'), 'extraData': ('uint16_t', 'H'),
               'smallFCD': ('uint8_t', 'B')}


def sha256(value):
    if not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('expected SHA-256 must be 64 lowercase hexadecimal digits')
    return value


def open_regular(path):
    # O_NONBLOCK prevents a Unix FIFO from blocking before its type is checked.
    # O_BINARY avoids platform text translation when using os.open on Windows.
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)
                         | getattr(os, 'O_BINARY', 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError('input must be a regular file')
        return os.fdopen(descriptor, 'rb')
    except BaseException:
        os.close(descriptor)
        raise


def numeric_list(body, count, code):
    fields = body.strip().split(',')
    if len(fields) != count or not all(
            re.fullmatch(r'(?:0x[0-9a-fA-F]+|0|[1-9][0-9]*)', field.strip())
            for field in fields):
        raise ValueError('unsupported numeric initializer or element count')
    try:
        return struct.pack('<' + str(count) + code,
                           *(int(field.strip(), 0) for field in fields))
    except (ValueError, struct.error, OverflowError) as error:
        raise ValueError('initializer value outside declared width') from error


def arrays(source):
    """Recognize the pinned generated spelling; do not interpret arbitrary C++."""
    if len(source) > SOURCE_CAP:
        raise ValueError('source size cap')
    text = source.decode('utf-8')
    formats = re.findall(
        r'^static const UVersionInfo norm2_nfc_data_formatVersion=\{([^{}]+)\};$',
        text, re.M)
    if len(formats) != 1:
        raise ValueError('missing or duplicate format declaration')
    fmt = numeric_list(formats[0], 4, 'B')
    if fmt not in (b'\x04\0\0\0', b'\x05\0\0\0'):
        raise ValueError('unsupported generated data format')
    index_count = {4: 20, 5: 22}[fmt[0]]
    declarations = re.findall(
        r'^static const (int32_t|uint16_t|uint8_t) '
        r'norm2_nfc_data_(\w+)\[([^\]\n]+)\]=\{\s*([^{}]+?)\s*\};', text, re.M)
    result = {}
    for kind, name, count_text, body in declarations:
        if name not in ARRAY_TYPES or name in result or kind != ARRAY_TYPES[name][0]:
            raise ValueError('unexpected or duplicate array declaration')
        if name == 'indexes':
            if count_text != 'Normalizer2Impl::IX_COUNT':
                raise ValueError('unsupported indexes declaration')
            count = index_count
        else:
            if not re.fullmatch(r'[1-9][0-9]{0,4}', count_text):
                raise ValueError('unsupported array length')
            count = int(count_text)
        if not 0 < count <= ELEMENT_CAP:
            raise ValueError('array length cap')
        result[name] = numeric_list(body, count, ARRAY_TYPES[name][1])
    if result.keys() != ARRAY_TYPES.keys():
        raise ValueError('missing arrays')
    return fmt[0], result


def inspect(source_path, binary_path, source_sha, binary_sha, offset=0, size=None):
    sha256(source_sha)
    sha256(binary_sha)
    if type(offset) is not int or offset < 0 or (
            size is not None and (type(size) is not int or size <= 0)):
        raise ValueError('invalid region')
    with open_regular(source_path) as stream:
        source = stream.read(SOURCE_CAP + 1)
    if len(source) > SOURCE_CAP:
        raise ValueError('source size cap')
    if hashlib.sha256(source).hexdigest() != source_sha:
        raise ValueError('source identity mismatch')
    fmt, payloads = arrays(source)
    # Hash and capture the selected region in one bounded streaming pass, so
    # emitted locations refer to the bytes contributing to the reported hash.
    with open_regular(binary_path) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= BINARY_CAP:
            raise ValueError('binary file type or size cap')
        size = info.st_size - offset if size is None else size
        if not 0 < size <= REGION_CAP or offset + size > info.st_size:
            raise ValueError('region outside file or size cap')
        digest, region, total = hashlib.sha256(), bytearray(), 0
        while chunk := stream.read(min(CHUNK_SIZE, BINARY_CAP + 1 - total)):
            digest.update(chunk)
            lo, hi = max(offset, total), min(offset + size, total + len(chunk))
            if lo < hi:
                region.extend(chunk[lo - total:hi - total])
            total += len(chunk)
            if total > BINARY_CAP:
                raise ValueError('binary size cap')
        if total != info.st_size or len(region) != size:
            raise ValueError('binary size changed or short region')
        if digest.hexdigest() != binary_sha:
            raise ValueError('binary identity mismatch')
    matches = {}
    for name, payload in payloads.items():
        start, occurrences, locations = 0, 0, []
        while (found := region.find(payload, start)) >= 0:
            occurrences += 1
            if occurrences > MATCH_CAP:
                raise ValueError('array occurrence cap')
            if len(locations) < 8:
                locations.append(offset + found)
            start = found + 1
        matches[name] = {'elements': len(payload) // struct.calcsize(ARRAY_TYPES[name][1]),
                         'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
                         'occurrencesInRegion': occurrences, 'firstFileOffsets': locations}
    return {'sourceSha256': source_sha, 'binarySha256': binary_sha,
            'binaryBytes': total, 'regionOffset': offset, 'regionBytes': size,
            'formatMajor': fmt, 'arrays': matches,
            'allArraysLocated': all(item['occurrencesInRegion'] > 0 for item in matches.values()),
            'nativeUseProven': False, 'normalizationProfileProven': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--binary-sha256', required=True)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--size', type=int)
    args = parser.parse_args()
    try:
        report = inspect(args.source, args.binary, args.source_sha256,
                         args.binary_sha256, args.offset, args.size)
    except (OSError, ValueError) as error:
        parser.exit(1, f'inspection incomplete: {error}\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
