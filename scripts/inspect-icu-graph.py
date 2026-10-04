#!/usr/bin/env python3
"""Bounded structural graph research for one caller-declared ICU 78.1 root.

No tailoring/base objects, consumer attestation, offsets or acceptance table.
Reuses the bounded root decoder; graph keys are (CE32, exact scalar/sentinel)
within this single data object. Both caller and sentinel contraction results
are conservatively included for trie results. Defaults keep the caller scalar:
the top-level sentinel dispatch requires recorded skipped marks at a trie match.
No sampled suffixes.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location(
    'icu_mapping_reader', Path(__file__).with_name('inspect-icu-mappings.py'))
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
require, at, span = reader.require, reader.at, reader.span


class GraphFailure(reader.Unverified):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


class StructuralGraph:
    def __init__(self, root, max_nodes=2000000, max_depth=128, max_edges=4000000):
        self.root = root
        self.max_nodes, self.max_depth = max_nodes, max_depth
        self.max_edges = max_edges
        self.ranks = {}
        self.active = set()
        self.nodes_started = 0
        self.edges = 0

    def successors(self, value, cp):
        require(cp == -1 or (1 <= cp <= 0x10ffff and not 0xd800 <= cp <= 0xdfff),
                'invalid scalar/sentinel argument')
        require(0 <= value <= 0xffffffff and value != 1, 'invalid/internal CE32')
        low = value & 255
        tag = -1 if low < 0xc0 else value & 15
        index, length = value >> 13, (value >> 8) & 31
        root = self.root
        if tag in (-1, 1, 2):
            reader.direct_ce(value)
        elif tag == 4:
            pass  # Fixed two-CE Latin expansion, no recursive dispatch.
        elif tag == 5:
            for item in span(root.ce32s, index, length):
                require(item != 1, 'internal CE32 in expansion')
                reader.direct_ce(item)
        elif tag == 6:
            require(all(v != 0x101000100 for v in span(root.ces, index, length)),
                    'end sentinel in expansion')
        elif tag in (8, 9):
            default, *values = root.context_values(index)
            args = (cp,) if tag == 8 else tuple(dict.fromkeys((cp, -1)))
            return ((default, cp),) + tuple((v, c) for v in values for c in args)
        elif tag == 10:
            require((value >> 8) & 15 <= 9, 'digit value')
            return ((at(root.ce32s, index), cp),)
        elif tag == 12:
            require(0xac00 <= cp <= 0xd7a3, 'Hangul requires syllable')
            syllable = cp - 0xac00
            t = syllable % 28
            indices = [syllable // 588, 19 + ((syllable // 28) % 21)]
            if t:
                indices.append(39 + t)
            values = [at(root.jamo, i) for i in indices]
            if value & 0x100:
                require(all(v & 255 < 0xc0 and v != 1 for v in values),
                        'invalid fast Jamo')
                return ()  # Direct conversions, not calls in this branch.
            return tuple((v, -1) for v in values)
        elif tag == 14:
            require(cp != -1, 'offset requires scalar')
            at(root.ces, index)
        elif tag == 15:
            require(value == 0xffffffff and cp != -1, 'implicit encoding/scalar')
        else:
            # Includes canonical/noncanonical fallback: this reader has no base.
            raise GraphFailure('unsupported_dispatch', f'out-of-model tag {tag}')
        return ()

    def rank(self, value, cp):
        key = value, cp
        if key in self.active:
            raise GraphFailure('cycle', f'cycle at CE32 {value:#x}, scalar {cp}')
        if key in self.ranks:
            return self.ranks[key]
        if len(self.active) >= self.max_depth or self.nodes_started >= self.max_nodes:
            raise GraphFailure('budget', 'graph traversal bound')
        self.nodes_started += 1
        self.active.add(key)
        try:
            children = self.successors(value, cp)
            if self.edges + len(children) > self.max_edges:
                raise GraphFailure('budget', 'graph edge bound')
            self.edges += len(children)
            result = max((1 + self.rank(v, c) for v, c in children), default=0)
            self.ranks[key] = result  # Cache only fully checked subgraphs.
            return result
        finally:
            self.active.remove(key)


def scalars():
    yield from range(1, 0xd800)
    yield from range(0xe000, 0x110000)


def inspect(raw):
    root = reader.RootMappings(raw)
    graph = StructuralGraph(root)
    completed, cp, failure = 0, None, None
    try:
        for cp in scalars():
            # initial() also checks lead-unit shortcuts against the scalar entry.
            # Root-only: there can be no unresolved base or alternate data object.
            value = root.initial(cp)
            graph.rank(value, cp)
            completed += 1
    except reader.Unverified as error:
        kind = ('decoder_budget' if isinstance(error, reader.DecoderBudgetExceeded)
                else getattr(error, 'kind', 'unverified_data'))
        failure = {'kind': kind,
                   'reason': str(error), 'rootScalar': cp}
    complete = failure is None and completed == 0x110000 - 0x800 - 1
    return {'scope': 'single caller-declared ICU 78.1 little-endian UCol-v5 root payload',
            'inputProfileVerified': False, 'consumerIdentityProven': False,
            'acceptanceTable': False, 'offsetsProven': False,
            'consumerTerminationProven': False,
            'numericCollation': 'assumed off; only payload default checked',
            'allNonNulScalarRootsCompleted': complete,
            'structuralGraphAcyclic': True if complete else None,
            'rootCountCompleted': completed, 'failure': failure,
            'nodesCompleted': len(graph.ranks), 'nodesStarted': graph.nodes_started,
            'edgesExamined': graph.edges,
            'maxCompletedRank': max(graph.ranks.values(), default=0),
            'limits': {'nodes': graph.max_nodes, 'depth': graph.max_depth,
                       'edges': graph.max_edges},
            'contextTries': len(root.context_cache)}


def main():
    parser = reader.ResearchParser(description=__doc__)
    parser.add_argument('--root-data', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        require(args.root_data.stat().st_size <= 16 * 1024 * 1024, 'payload size')
        raw = args.root_data.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(digest == args.sha256.lower(), 'payload hash mismatch')
        result = inspect(raw)
        result['rootSha256'] = digest
    except (ValueError, OSError, struct.error) as error:
        parser.exit(1, f'unverified: {error}\n')
    print(json.dumps(result, indent=2))
    return 0 if result['allNonNulScalarRootsCompleted'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
