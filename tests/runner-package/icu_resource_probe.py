"""Bounded research ResB-v2 projection, not an effective-data proof.

Only selected-path metadata and fixed-token string comparisons are returned.
No alias/pool/fallback resolution, recursive traversal or arbitrary export.
"""
import struct

MEMBER_CAP = 4 * 1024 * 1024
TABLE_CAP = 4096
KEY_CAP = 256
STRING_CAP = 64


REASONS = {"layout", "format-version", "pool-or-index-layout", "container-type",
           "string-encoding", "limit"}


class UnsupportedResource(ValueError):
    pass


def require(value, reason="layout"):
    if not value:
        raise UnsupportedResource(reason)


class Resource:
    def __init__(self, member):
        require(len(member) <= MEMBER_CAP, "limit")
        require(32 <= len(member))
        h = struct.unpack_from("<H", member)[0]
        require(24 <= h <= len(member) - 32)
        info = struct.unpack_from("<H", member, 4)[0]
        require(20 <= info <= h - 4)
        require(member[2:4] == b"\xda\x27" and member[8:11] == b"\0\0\2")
        require(member[12:20] == b"ResB\2\0\0\0", "format-version")
        self.raw = member[h:]
        self.root = self.u32(0)
        n = self.u32(4)
        require(n == 7, "pool-or-index-layout")
        self.indexes = [self.u32(4 + i * 4) for i in range(n)]
        ix = self.indexes
        require(ix[5] in (0, 1), "pool-or-index-layout")
        require(8 <= ix[1] <= ix[6] <= ix[2] <= ix[3] <= len(self.raw) // 4)
        require(len(self.raw) - ix[3] * 4 < 16)
        self.raw = self.raw[:ix[3] * 4]
        self.key_end = ix[1] * 4
        self.units_end = ix[6] * 4
        self.resources_end = ix[2] * 4
        require(self.root >> 28 in (2, 4), "container-type")

    def u32(self, p):
        require(0 <= p <= len(self.raw) - 4)
        return struct.unpack_from("<I", self.raw, p)[0]

    def u16(self, p):
        require(0 <= p <= len(self.raw) - 2)
        return struct.unpack_from("<H", self.raw, p)[0]

    def key(self, p):
        require(32 <= p < self.key_end)
        end = self.raw.find(b"\0", p, min(p + KEY_CAP, self.key_end))
        require(end >= p)
        key = self.raw[p:end]
        require(key and all(32 <= b <= 126 for b in key))
        return key

    def lookup(self, resource, wanted):
        kind, offset = resource >> 28, resource & 0xfffffff
        require(kind in (2, 4), "container-type")
        if not offset:
            return None
        p = offset * 4
        require(p >= self.units_end)
        width = 2 if kind == 2 else 4
        read = self.u16 if kind == 2 else self.u32
        count = read(p)
        require(count <= TABLE_CAP, "limit")
        values = (p + width * (count + 1) + 3) & ~3
        require(values + count * 4 <= self.resources_end)
        previous = b""
        found = None
        for i in range(count):
            key = self.key(read(p + width * (i + 1)))
            require(key > previous)
            previous = key
            if key == wanted:
                found = self.u32(values + i * 4)
        return found

    def string_v2(self, resource):
        if resource == 0:  # genrb's empty URES_STRING encoding.
            return ()
        require(resource >> 28 == 6, "string-encoding")
        p = self.key_end + 2 * (resource & 0xfffffff)
        require(self.key_end <= p <= self.units_end - 2)
        first = self.u16(p)
        # This draft only accepts short implicit strings, not encoded lengths.
        require(not 0xdc00 <= first <= 0xdfff, "string-encoding")
        units = []
        for _ in range(STRING_CAP):
            require(p <= self.units_end - 2)
            unit = self.u16(p)
            p += 2
            if not unit:
                return tuple(units)
            units.append(unit)
        raise UnsupportedResource("limit")

    def projection(self):
        collations = self.lookup(self.root, b"collations")
        result = {"attributes": self.indexes[5], "rootType": self.root >> 28,
                  "rootOffsetZero": (self.root & 0xfffffff) == 0,
                  "collationsPresent": collations is not None}
        if collations is None:
            return result
        default = self.lookup(collations, b"default")
        standard = self.lookup(collations, b"standard")
        result["defaultPresent"] = default is not None
        result["standardPresent"] = standard is not None
        if default is not None:
            result["defaultIsStandard"] = self.string_v2(default) == tuple(map(ord, "standard"))
        if standard is not None:
            result["standardType"] = standard >> 28
        return result


def project_resource(member):
    try:
        return {"status": "observed-selected-fields", **Resource(member).projection()}
    except UnsupportedResource as error:
        reason = str(error) if str(error) in REASONS else "layout"
        return {"status": "unavailable", "reason": reason}
    except (ValueError, struct.error):
        return {"status": "unavailable", "reason": "layout"}
