"""Offline ELF64-LE ICU package inspection; no loading or raw-data output.

The caller supplies a separately verified file hash and exported-symbol span.
This maps that span through PT_LOAD; it does not discover/authenticate symbols
or establish native loader selection. TOC checks reuse icu_package_inventory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

import icu_package_inventory

FILE_CAP = 64 * 1024 * 1024
PH_CAP = 1024


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def mapped_span(raw, address, size):
    require(len(raw) >= 64, "elf-header")
    require(raw[:7] == b'\x7fELF\x02\x01\x01', "elf-format")
    kind, machine, version = struct.unpack_from('<HHI', raw, 16)
    require((kind, machine, version) == (3, 62, 1), "elf-target")
    phoff = struct.unpack_from('<Q', raw, 32)[0]
    ehsize, entsize, count = struct.unpack_from('<HHH', raw, 52)
    require(ehsize == 64 and entsize == 56 and 0 < count <= PH_CAP, "elf-program-table")
    require(64 <= phoff <= len(raw) - count * entsize, "elf-program-table")
    require(0 <= address < 2**64 and 0 < size <= FILE_CAP and address + size <= 2**64,
            "symbol-span")
    candidates = []
    overlaps = 0
    for index in range(count):
        ptype, flags, offset, va, _, filesz, memsz, align = struct.unpack_from(
            '<IIQQQQQQ', raw, phoff + index * entsize)
        if ptype != 1:
            continue
        require(filesz <= memsz and offset <= len(raw) - filesz
                and va + memsz <= 2**64, "elf-load-bounds")
        if address < va + memsz and va < address + size:
            overlaps += 1
        if va <= address and address + size <= va + filesz:
            candidates.append(offset + address - va)
    require(overlaps == 1 and len(candidates) == 1, "symbol-file-mapping")
    return candidates[0]


def inspect(raw, expected_sha256, address, size, prefix):
    require(0 < len(raw) <= FILE_CAP, "file-size-limit")
    require(re.fullmatch('[0-9a-f]{64}', expected_sha256) is not None, "expected-sha256")
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == expected_sha256, "file-hash-mismatch")
    offset = mapped_span(raw, address, size)
    package = icu_package_inventory.inventory(raw[offset:offset + size], prefix)
    return {'status': 'observed-package', 'fileSha256': digest,
            'suppliedSymbolVA': address, 'suppliedSymbolSize': size,
            'symbolFileOffset': offset, 'package': package}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(1, 'unverified: invalid arguments\n')


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--symbol-va', required=True, type=lambda s: int(s, 0))
    parser.add_argument('--symbol-size', required=True, type=lambda s: int(s, 0))
    parser.add_argument('--prefix', required=True, choices=('icudt70l', 'icudt74l'))
    args = parser.parse_args()
    try:
        with args.file.open('rb') as stream:
            raw = stream.read(FILE_CAP + 1)
        result = inspect(raw, args.sha256, args.symbol_va, args.symbol_size, args.prefix)
    except OSError:
        print('unverified: file-read-error', file=sys.stderr)
        return 1
    except ValueError as error:
        print(f'unverified: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
