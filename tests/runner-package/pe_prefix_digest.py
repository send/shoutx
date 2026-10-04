"""Research draft: bounded byte comparison, NOT an Authenticode verifier.

This hashes every byte before a terminal certificate table after zeroing only
the checksum and security-directory entry. Comparing results requires equal
prefix lengths and excluded-field offsets as well as equal digests. It does
not establish equivalent loading, signatures, effective ICU data or behavior.
"""
import hashlib
import struct


def prefix_digest(data):
    if not 64 <= len(data) <= 8 * 1024 * 1024 or data[:2] != b"MZ":
        raise ValueError("prefix-layout")
    pe = struct.unpack_from("<I", data, 60)[0]
    if not 64 <= pe <= len(data) - 24 or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("prefix-layout")
    machine, count = struct.unpack_from("<HH", data, pe + 4)
    size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    section_table = optional + size
    if (machine != 0x8664 or not 1 <= count <= 96 or size < 152
            or section_table + count * 40 > len(data)):
        raise ValueError("prefix-layout")
    if struct.unpack_from("<H", data, optional)[0] != 0x20B:
        raise ValueError("prefix-layout")
    directories = struct.unpack_from("<I", data, optional + 108)[0]
    if not 5 <= directories <= (size - 112) // 8:
        raise ValueError("prefix-layout")
    checksum = optional + 64
    security = optional + 144
    start, length = struct.unpack_from("<II", data, security)
    headers = struct.unpack_from("<I", data, optional + 60)[0]
    if (not section_table + count * 40 <= headers <= start
            or start % 8 or length < 8 or start + length != len(data)):
        raise ValueError("prefix-certificate-bounds")
    # Excluded certificate bytes must not overlap any declared raw section.
    for index in range(count):
        raw_size, raw_start = struct.unpack_from("<II", data, section_table + index * 40 + 16)
        if raw_size and not headers <= raw_start <= raw_start + raw_size <= start:
            raise ValueError("prefix-section-bounds")
    cursor = start
    certificates = 0
    while cursor < len(data):
        if len(data) - cursor < 8:
            raise ValueError("prefix-certificate-entry")
        entry_size = struct.unpack_from("<I", data, cursor)[0]
        aligned = (entry_size + 7) & ~7
        if entry_size < 8 or cursor + aligned > len(data):
            raise ValueError("prefix-certificate-entry")
        cursor += aligned
        certificates += 1
    prefix = bytearray(data[:start])
    prefix[checksum:checksum + 4] = bytes(4)
    prefix[security:security + 8] = bytes(8)
    return {"algorithm": "pe32plus-terminal-certificate-zeroed-prefix-v1",
            "prefixSize": start, "checksumOffset": checksum,
            "securityDirectoryOffset": security,
            "certificateSize": length, "certificateCount": certificates,
            "sha256": hashlib.sha256(prefix).hexdigest()}
