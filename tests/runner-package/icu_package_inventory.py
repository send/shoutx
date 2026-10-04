"""Research draft: bounded CmnD-v1 offset inventory, not resource semantics.

No member payload bytes or full name table are returned. Storage intervals include
headers and padding. The final entry has no next-offset length in this format.
"""
import hashlib
import struct

import icu_resource_probe

SELECTED = ("coll/en.res", "coll/en_US.res", "coll/root.res", "coll/ucadata.icu", "nfc.nrm",
            "nfkc.nrm", "brkitr/root.res", "brkitr/char.brk")
MAX_ENTRIES = 100000
NAME_CAP = 1024


def require(condition):
    if not condition:
        raise ValueError("unsupported-package-layout")


def header(data, start, end):
    require(0 <= start <= end - 24 and end <= len(data))
    size, info_size = struct.unpack_from("<H2xH", data, start)
    require(data[start + 2:start + 4] == b"\xda\x27")
    require(data[start + 8:start + 11] == bytes((0, 0, 2)))
    require(20 <= info_size <= size - 4 and size <= end - start)
    return {"headerSize": size, "formatHex": data[start + 12:start + 16].hex(),
            "formatVersion": list(data[start + 16:start + 20]),
            "dataVersion": list(data[start + 20:start + 24])}


def inventory(data, prefix):
    require(24 <= len(data) <= 64 * 1024 * 1024)
    require(prefix in ("icudt70l", "icudt72l", "icudt74l", "icudt76l"))
    h = header(data, 0, len(data))
    require(h["formatHex"] == b"CmnD".hex() and h["formatVersion"] == [1, 0, 0, 0])
    base = h["headerSize"]
    require(base <= len(data) - 4)
    count = struct.unpack_from("<I", data, base)[0]
    require(1 <= count <= MAX_ENTRIES and base + 4 + count * 8 <= len(data))
    entries = [struct.unpack_from("<II", data, base + 4 + index * 8) for index in range(count)]
    first_data = base + entries[0][1]
    names_start = base + 4 + count * 8
    require(names_start <= first_data <= len(data) - 24)
    selected = {f"{prefix}/{suffix}".encode("ascii"): suffix for suffix in SELECTED}
    rows = {}
    prefix_count = 0
    previous_name = b""
    previous_data = first_data - 1
    for index, (name_offset, data_offset) in enumerate(entries):
        name_start, item_start = base + name_offset, base + data_offset
        require(names_start <= name_start < first_data)
        name_end = data.find(b"\0", name_start, min(first_data, name_start + NAME_CAP))
        require(name_end >= name_start)
        name = bytes(data[name_start:name_end])
        require(name > previous_name and all(32 <= byte <= 126 for byte in name))
        require(previous_data < item_start <= len(data) - 24)
        previous_name, previous_data = name, item_start
        prefix_count += name.startswith((prefix + "/").encode("ascii"))
        if name not in selected:
            continue
        suffix = selected[name]
        if index + 1 == count:
            rows[suffix] = {"status": "last-entry-length-unknown", "offset": item_start}
            continue
        item_end = base + entries[index + 1][1]
        require(item_start < item_end <= len(data))
        item_header = header(data, item_start, item_end)
        rows[suffix] = {"status": "observed-storage", "offset": item_start,
                        "size": item_end - item_start,
                        "sha256": hashlib.sha256(data[item_start:item_end]).hexdigest(),
                        **item_header}
        if suffix in ("coll/en.res", "coll/en_US.res", "coll/root.res"):
            rows[suffix]["resource"] = (
                icu_resource_probe.project_resource(data[item_start:item_end])
                if item_end - item_start <= icu_resource_probe.MEMBER_CAP
                else {"status": "unavailable", "reason": "limit"})
    if not prefix_count:
        raise ValueError("prefix-mismatch")
    return {"packageHeader": h, "entryCount": count, "prefixNameCount": prefix_count,
            "members": {suffix: rows.get(suffix, {"status": "absent"}) for suffix in SELECTED}}
