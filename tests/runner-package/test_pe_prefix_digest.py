import hashlib
import struct
import unittest

from pe_prefix_digest import prefix_digest


def fixture():
    data = bytearray(800)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<HH", data, 68, 0x8664, 1)
    struct.pack_into("<H", data, 84, 240)
    struct.pack_into("<H", data, 88, 0x20B)
    struct.pack_into("<I", data, 148, 512)
    struct.pack_into("<I", data, 196, 16)
    struct.pack_into("<II", data, 232, 768, 32)
    struct.pack_into("<II", data, 344, 256, 512)
    struct.pack_into("<IHH", data, 768, 32, 0x200, 2)
    return data


class PrefixTests(unittest.TestCase):
    def test_exact_digest_and_included_bytes(self):
        data = fixture()
        # Independently construct the exact byte sequence from fixture offsets.
        expected = data[:152] + bytes(4) + data[156:232] + bytes(8) + data[240:768]
        baseline = prefix_digest(data)
        self.assertEqual(baseline["sha256"], hashlib.sha256(expected).hexdigest())
        self.assertEqual(baseline["prefixSize"], 768)
        for offset in (40, 147, 156, 231, 240, 400, 511, 512, 767):
            changed = bytearray(data)
            changed[offset] ^= 1
            with self.subTest(offset=offset):
                self.assertNotEqual(prefix_digest(changed)["sha256"], baseline["sha256"])

    def test_only_explicit_exclusions(self):
        data = fixture()
        baseline = prefix_digest(data)
        for offset in (152, 153, 154, 155, 776, 799):
            changed = bytearray(data)
            changed[offset] ^= 1
            self.assertEqual(prefix_digest(changed)["sha256"], baseline["sha256"])
        data.extend(bytes(16))
        struct.pack_into("<I", data, 236, 48)
        struct.pack_into("<I", data, 768, 48)
        result = prefix_digest(data)
        self.assertEqual(result["sha256"], baseline["sha256"])
        self.assertNotEqual(result["certificateSize"], baseline["certificateSize"])

    def test_gaps_and_overlay_are_included(self):
        data = fixture()
        struct.pack_into("<II", data, 344, 240, 520)
        baseline = prefix_digest(data)["sha256"]
        for offset in (516, 764):  # Header-to-section gap, then trailing overlay.
            changed = bytearray(data)
            changed[offset] ^= 1
            with self.subTest(offset=offset):
                self.assertNotEqual(prefix_digest(changed)["sha256"], baseline)

    def test_fail_closed_layouts(self):
        cases = [(60, "I", 0), (60, "I", 2**32-1), (68, "H", 0xaa64),
                 (70, "H", 0), (70, "H", 97), (84, "H", 151),
                 (84, "H", 65535), (88, "H", 0x10b), (196, "I", 4),
                 (196, "I", 17), (148, "I", 367), (148, "I", 769),
                 (232, "I", 769), (232, "I", 512), (236, "I", 0),
                 (236, "I", 31), (344, "I", 257), (348, "I", 511),
                 (348, "I", 2**32-1), (768, "I", 0), (768, "I", 7),
                 (768, "I", 33), (768, "I", 2**32-1)]
        for offset, kind, value in cases:
            data = fixture()
            struct.pack_into("<"+kind, data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                prefix_digest(data)
        for data in (b"", b"MZ", fixture()[:100], fixture() + b"x"):
            with self.assertRaises(ValueError):
                prefix_digest(data)

    def test_multiple_aligned_entries(self):
        data = fixture()
        struct.pack_into("<I", data, 768, 9)
        struct.pack_into("<IHH", data, 784, 16, 0x200, 2)
        self.assertEqual(prefix_digest(data)["certificateCount"], 2)
        struct.pack_into("<I", data, 784, 17)
        with self.assertRaises(ValueError):
            prefix_digest(data)

    def test_isolated_bounds_and_cap(self):
        data = fixture() + bytes(4)
        struct.pack_into("<II", data, 232, 772, 32)
        struct.pack_into("<IHH", data, 772, 32, 0x200, 2)
        with self.assertRaisesRegex(ValueError, "^prefix-certificate-bounds$"):
            prefix_digest(data)  # Only certificate alignment is invalid.
        data = fixture()
        struct.pack_into("<I", data, 344, 0)
        struct.pack_into("<I", data, 148, 769)
        with self.assertRaisesRegex(ValueError, "^prefix-certificate-bounds$"):
            prefix_digest(data)  # Empty section cannot mask the header bound.
        data = fixture()[:768]
        struct.pack_into("<I", data, 236, 0)
        with self.assertRaisesRegex(ValueError, "^prefix-certificate-bounds$"):
            prefix_digest(data)  # EOF matches; certificate length is invalid.
        data = fixture()
        data.extend(bytes(8 * 1024 * 1024 - len(data)))
        struct.pack_into("<I", data, 236, len(data) - 768)
        struct.pack_into("<I", data, 768, len(data) - 768)
        self.assertEqual(prefix_digest(data)["prefixSize"], 768)
        with self.assertRaisesRegex(ValueError, "^prefix-layout$"):
            prefix_digest(data + b"x")
        for offset in range(232, 240):
            data = fixture()
            data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                prefix_digest(data)  # Cannot zero a malformed directory away.


if __name__ == "__main__":
    unittest.main()
