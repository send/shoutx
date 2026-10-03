#!/usr/bin/env python3
"""Offline ICU 78.1 root-mapping research; never emits an acceptance table.

Input is a separately acquired little-endian UCol-v5 root payload WITHOUT its
UDataInfo header. Hash matching identifies bytes, not the consumer using them.
The decoder follows release-78.1 collation.h, collationdata.h,
collationdatareader.h, utrie2.h, utrie2_impl.h, utrie2.cpp, ucharstrie.h and
ucharstrieiterator.cpp from unicode-org/icu. Execution semantics are taken
from collationiterator.cpp, coleitr.cpp, utf16collationiterator.cpp and
collationsettings.h in the same release.
All prefix/default/contraction alternatives are included conservatively, not
filtered by a header. This is data-graph analysis, not an iterator-offset proof.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct


class Unverified(ValueError):
    """Unsupported or malformed evidence must not become positive evidence."""


class ResearchParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(1, f'unverified: {message}\n')


def require(condition, message):
    if not condition:
        raise Unverified(message)


def at(values, index):
    require(0 <= index < len(values), "reference outside section")
    return values[index]


def span(values, start, length):
    require(length > 0 and 0 <= start <= len(values) - length,
            "invalid referenced span")
    return values[start:start + length]


class ContextTrie:
    """Bounded UCharsTrie enumeration, including intermediate values."""
    def __init__(self, units, max_visits=100000, max_key=64):
        self.units = units
        self.max_visits = max_visits
        self.max_key = max_key
        self.visits = 0

    def tick(self, depth):
        self.visits += 1
        require(self.visits <= self.max_visits and depth <= 128,
                "context traversal bound")

    def value(self, pos, lead):
        if lead < 0x4000:
            return lead, pos
        if lead < 0x7fff:
            return ((lead - 0x4000) << 16) | at(self.units, pos), pos + 1
        return (at(self.units, pos) << 16) | at(self.units, pos + 1), pos + 2

    def delta(self, pos):
        lead = at(self.units, pos)
        pos += 1
        if lead < 0xfc00:
            return lead, pos
        if lead < 0xffff:
            return ((lead - 0xfc00) << 16) | at(self.units, pos), pos + 1
        return (at(self.units, pos) << 16) | at(self.units, pos + 1), pos + 2

    def branch(self, pos, length, key, depth):
        self.tick(depth)
        require(2 <= length <= 65536, "branch length")
        if length > 5:
            at(self.units, pos)  # Comparison unit, both alternatives are visited.
            delta, after = self.delta(pos + 1)
            yield from self.branch(after + delta, length // 2, key, depth + 1)
            yield from self.branch(after, length - length // 2, key, depth + 1)
            return
        for _ in range(length - 1):
            unit, lead = at(self.units, pos), at(self.units, pos + 1)
            value, pos = self.value(pos + 2, lead & 0x7fff)
            child = key + (unit,)
            require(len(child) <= self.max_key, "context key bound")
            if lead & 0x8000:
                yield child, value
            else:
                yield from self.node(pos + value, child, depth + 1)
        yield from self.node(pos + 1, key + (at(self.units, pos),), depth + 1)

    def node(self, pos, key=(), depth=0):
        self.tick(depth)
        require(len(key) <= self.max_key, "context key bound")
        lead = at(self.units, pos)
        pos += 1
        if lead & 0x8000:
            value, _ = self.value(pos, lead & 0x7fff)
            yield key, value
            return
        if lead >= 0x40:
            if lead < 0x4040:
                value = (lead >> 6) - 1
            elif lead < 0x7fc0:
                value = (((lead & 0x7fc0) - 0x4040) << 10) | at(self.units, pos)
                pos += 1
            else:
                value = (at(self.units, pos) << 16) | at(self.units, pos + 1)
                pos += 2
            yield key, value
        node = lead & 0x3f
        if node < 0x30:
            if node == 0:
                node = at(self.units, pos)
                pos += 1
            yield from self.branch(pos, node + 1, key, depth + 1)
        else:
            length = node - 0x30 + 1
            units = span(self.units, pos, length)
            yield from self.node(pos + length, key + tuple(units), depth + 1)

    def entries(self, start):
        result = list(self.node(start))
        require(result and len({key for key, _ in result}) == len(result),
                "empty or duplicate context keys")
        return result


def first_half(ce):
    return ((ce >> 32) & 0xffff0000) | ((ce >> 16) & 0xff00) | ((ce >> 8) & 0xff)


def direct_ce(value):
    low = value & 255
    if low < 0xc0:
        return ((value & 0xffff0000) << 32) | ((value & 0xff00) << 16) | (low << 8)
    if low == 0xc1:
        return ((value & 0xffffff00) << 32) | 0x05000500
    if low == 0xc2:
        return value & 0xffffff00
    raise Unverified("non-direct CE32 in direct expansion")


class RootMappings:
    def __init__(self, raw):
        require(80 <= len(raw) <= 16 * 1024 * 1024, "payload size")
        self.indexes = indexes = struct.unpack_from('<20i', raw)
        require(indexes[0] == 20 and indexes[5] >= 80, "root index header")
        require(all(0 <= a <= b <= len(raw) for a, b in zip(indexes[5:19], indexes[6:20])),
                "section bounds")
        require(0 <= len(raw) - indexes[19] < 16, "payload slack")

        def section(index, width, code):
            begin, end = indexes[index:index + 2]
            require((end - begin) % width == 0 and begin % width == 0,
                    "section alignment")
            return struct.unpack_from('<' + str((end - begin) // width) + code, raw, begin)

        trie = raw[indexes[7]:indexes[8]]
        require(indexes[7] % 8 == 0 and len(trie) % 8 == 0, "trie section alignment")
        require(len(trie) >= 16, "truncated trie header")
        sig, options, ni, nd4, _, _, high = struct.unpack_from('<I6H', trie)
        nd = nd4 << 2
        require(sig == 0x54726932 and options == 1 and ni >= 2112 and nd >= 192,
                "unsupported trie header")
        require(0 <= len(trie) - (16 + ni * 2 + nd * 4) < 8 and high << 11 <= 0x110000,
                "trie size/high start")
        self.ti = struct.unpack_from(f'<{ni}H', trie, 16)
        self.td = struct.unpack_from(f'<{nd}I', trie, 16 + ni * 2)
        self.high = high << 11
        self.ces = section(9, 8, 'Q')
        self.ce32s = section(11, 4, 'I')
        self.contexts = section(13, 2, 'H')
        self.jamo = span(self.ce32s, indexes[4], 67)
        require(indexes[1] & 2 == 0, "numeric collation is outside this model")
        self.context_cache = {}
        self.context_entry_count = 0
        self.mapping_visits = 0
        self.memo = {}
        self.tags = Counter()

    def lookup(self, cp, lead_unit=False):
        require(0 <= cp <= 0x10ffff, "code point range")
        if cp <= 0xffff:
            require(lead_unit or not 0xd800 <= cp <= 0xdfff, "surrogate code point")
            index = (at(self.ti, cp >> 5) << 2) + (cp & 31)
        elif cp >= self.high:
            index = len(self.td) - 4
        else:
            block = at(self.ti, 2112 - 32 + (cp >> 11))
            index = (at(self.ti, block + ((cp >> 5) & 63)) << 2) + (cp & 31)
        return at(self.td, index)

    def initial(self, cp):
        value = self.lookup(cp)
        if cp > 0xffff:
            lead = self.lookup(0xd800 + ((cp - 0x10000) >> 10), lead_unit=True)
            require(lead & 0xff == 0xcd and lead < 0x400, "lead-unit tag")
            summary = lead & 0x300
            if summary == 0:
                require(value == 0xffffffff, "implicit lead summary mismatch")
                return 0xffffffff
            require(summary != 0x100, "root lead summary requires missing base")
        return value

    def context_values(self, index):
        if index not in self.context_cache:
            require(len(self.context_cache) < 4096, "context count bound")
            default = (at(self.contexts, index) << 16) | at(self.contexts, index + 1)
            entries = ContextTrie(self.contexts).entries(index + 2)
            self.context_entry_count += len(entries)
            require(self.context_entry_count <= 100000, "total context entry bound")
            self.context_cache[index] = (default, entries)
        default, entries = self.context_cache[index]
        return (default,) + tuple(value for _, value in entries)

    def leading(self, value, cp, active=frozenset()):
        """Possible zero/nonzero first raw halves; not offset/acceptance facts."""
        key = value, cp
        require(key not in active and len(active) < 64, "mapping cycle/depth")
        if key in self.memo:
            return self.memo[key]
        self.mapping_visits += 1
        require(self.mapping_visits <= 500000, "mapping traversal bound")
        require(value != 1, "internal no-mapping sentinel")
        active = active | {key}
        low = value & 255
        tag = -1 if low < 0xc0 else value & 15
        self.tags[str(tag)] += 1
        index, length = value >> 13, (value >> 8) & 31
        child = lambda v, c=cp: self.leading(v, c, active)
        if tag in (-1, 1, 2):
            result = {bool(first_half(direct_ce(value)))}
        elif tag == 4:
            ce = ((value & 0xff000000) << 32) | 0x05000000 | ((value & 0xff0000) >> 8)
            result = {bool(first_half(ce))}
        elif tag == 5:
            items = span(self.ce32s, index, length)
            converted = [direct_ce(v) for v in items]  # Validate the entire expansion.
            result = {bool(first_half(converted[0]))}
        elif tag == 6:
            items = span(self.ces, index, length)
            require(all(v != 0x101000100 for v in items), "end sentinel in expansion")
            result = {bool(first_half(items[0]))}
        elif tag in (8, 9):
            result = set()
            for alternative in self.context_values(index):
                # The discontiguous path can append with U_SENTINEL rather
                # than the initial scalar. Do not invent a scalar for any
                # contraction alternative that needs one, including default.
                result.update(child(alternative, -1 if tag == 9 else cp))
        elif tag == 10:
            require((value >> 8) & 15 <= 9, "digit value")
            result = child(at(self.ce32s, index))  # Numeric collation must be OFF.
        elif tag == 12:
            require(0xac00 <= cp <= 0xd7a3, "Hangul mapping without syllable")
            syllable = cp - 0xac00
            t = syllable % 28
            indices = [syllable // 588, 19 + ((syllable // 28) % 21)]
            if t:
                indices.append(39 + t)
            items = [at(self.jamo, i) for i in indices]
            if value & 0x100:
                require(all(v & 255 < 0xc0 for v in items), "special Jamo in fast path")
            outcomes = [child(v, -1) for v in items]  # Validate trailing Jamo too.
            result = outcomes[0]
        elif tag == 14:
            require(cp >= 0, "offset mapping needs code point")
            at(self.ces, index)
            # getCEFromOffsetCE32/makeCE adds common secondary/tertiary.
            # Those bits make the first 32-bit half nonzero, whatever primary.
            result = {True}
        elif tag == 15:
            require(value == 0xffffffff and cp >= 0, "implicit mapping encoding")
            result = {True}  # unassignedCEFromCodePoint also uses makeCE.
        else:
            raise Unverified(f"unsupported mapping tag {tag} (root-only reader)")
        self.memo[key] = frozenset(result)
        return self.memo[key]


def inspect(raw, candidates):
    root = RootMappings(raw)
    counts, reasons = Counter(), Counter()
    zero, unresolved = [], []
    for cp in candidates:
        require(1 <= cp <= 0x10ffff and not 0xd800 <= cp <= 0xdfff, "candidate scalar")
        try:
            outcomes = root.leading(root.initial(cp), cp)
        except Unverified as error:
            counts['unverified'] += 1
            reasons[str(error)] += 1
            if len(unresolved) < 32:
                unresolved.append(cp)
            continue
        if False in outcomes:
            counts['zero_first_half_possible'] += 1
            zero.append(cp)
        else:
            counts['nonzero_first_half_for_enumerated_mappings'] += 1
    return {'scope': 'caller-declared root data graph; not a consumer safety proof',
            'inputProfileVerified': False,
            'assumptions': {'inputProfile': 'ICU 78.1 little-endian UCol-v5 root payload without header',
                            'numericCollation': 'off; only payload default checked, not effective consumer attribute'},
            'acceptanceTable': False, 'offsetsProven': False, 'consumerIdentityProven': False,
            'candidateCount': len(candidates), 'classification': dict(counts),
            'unverifiedReasons': dict(reasons), 'unverifiedExamples': unresolved,
            'zeroFirstHalfPossible': zero, 'visitedMappingTags': dict(sorted(root.tags.items())),
            'contextTries': len(root.context_cache),
            'contextEntries': sum(len(entries) for _, entries in root.context_cache.values())}


def main():
    parser = ResearchParser(description=__doc__)
    parser.add_argument('--root-data', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    args = parser.parse_args()
    try:
        require(args.root_data.stat().st_size <= 16 * 1024 * 1024, 'payload size')
        raw = args.root_data.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(digest == args.sha256.lower(), 'payload hash mismatch')
        require(args.candidates.stat().st_size <= 1024 * 1024, 'candidate file size')
        candidate_bytes = args.candidates.read_bytes()
        ranges = json.loads(candidate_bytes)['ranges']
        candidates = []
        previous = 0
        for a, b in ranges:
            require(type(a) is int and type(b) is int and previous < a <= b <= 0x10ffff,
                    'candidate ranges')
            require(b < 0xd800 or a > 0xdfff, 'surrogate candidate range')
            candidates.extend(range(a, b + 1))
            previous = b
        require(candidates, 'empty candidates')
        result = inspect(raw, candidates)
        result.update(rootSha256=digest, candidateSha256=hashlib.sha256(candidate_bytes).hexdigest())
    except (ValueError, OSError, KeyError, TypeError, struct.error) as error:
        parser.exit(1, f'unverified: {error}\n')
    print(json.dumps(result, indent=2))
    return 2 if result['classification'].get('unverified') else 0


if __name__ == '__main__':
    raise SystemExit(main())
