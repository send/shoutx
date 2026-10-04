import hashlib
import struct
import unittest
from unittest.mock import patch
from test_icu_resource_probe import fixture as resource_fixture

import icu_package_inventory as probe


def fixture():
    data = bytearray(496)
    def header(offset, size, kind, version):
        struct.pack_into("<H2sHH4B", data, offset, size, b"\xda\x27", 20, 0, 0, 0, 2, 0)
        data[offset + 12:offset + 16] = kind
        data[offset + 16:offset + 20] = bytes((version, 0, 0, 0))
    header(0, 144, b"CmnD", 1)
    struct.pack_into("<I", data, 144, 3)
    cursor = 172
    for index, name in enumerate((b"icudt72l/coll/en.res", b"icudt72l/coll/root.res", b"icudt72l/zzz")):
        start = 256 + index * 80
        struct.pack_into("<II", data, 148 + index * 8, cursor - 144, start - 144)
        data[cursor:cursor + len(name) + 1] = name + b"\0"
        cursor += len(name) + 1
        header(start, 32, b"ResB", 2)
    return data


class PackageTests(unittest.TestCase):
    def test_fixed_projection_and_storage_intervals(self):
        data = fixture()
        r = probe.inventory(data, "icudt72l")
        self.assertEqual(r["entryCount"], 3)
        self.assertEqual(r["prefixNameCount"], 3)
        self.assertEqual(set(r), {"packageHeader", "entryCount", "prefixNameCount", "members"})
        self.assertEqual(set(r["members"]), set(probe.SELECTED))
        member = r["members"]["coll/en.res"]
        self.assertEqual(set(member), {"status", "offset", "size", "sha256", "headerSize", "formatHex", "formatVersion", "dataVersion", "resource"})
        self.assertEqual(member["resource"], {"status": "unavailable", "reason": "pool-or-index-layout"})
        self.assertEqual(member["offset"], 256)
        self.assertEqual(member["size"], 80)
        self.assertEqual(member["headerSize"], 32)
        self.assertEqual(member["sha256"], hashlib.sha256(data[256:336]).hexdigest())
        self.assertEqual(r["members"]["nfc.nrm"], {"status": "absent"})

    def test_top_header_and_bounds_rejected(self):
        for offset, kind, value in [(0,"H",23),(4,"H",19),(8,"B",1),(9,"B",1),
                                    (10,"B",4),(16,"B",2),(144,"I",0),(144,"I",100001),
                                    (148,"I",0),(152,"I",0),(152,"I",2**32-1),
                                    (160,"I",100),(256,"H",81)]:
            data = fixture()
            struct.pack_into("<"+kind,data,offset,value)
            with self.subTest(offset=offset,value=value), self.assertRaises(ValueError):
                probe.inventory(data,"icudt72l")
        for data in (b"", fixture()[:160], fixture()[:330]):
            with self.assertRaises(ValueError):
                probe.inventory(data,"icudt72l")

    def test_duplicate_names_and_unterminated_names_rejected(self):
        data = fixture()
        data[156:160] = data[148:152]
        with self.assertRaises(ValueError):
            probe.inventory(data,"icudt72l")
        data = fixture()
        data[172:256] = b"x" * 84
        with self.assertRaises(ValueError):
            probe.inventory(data,"icudt72l")

    def test_selected_last_entry_has_no_invented_length(self):
        data = fixture()
        name_start = 144 + struct.unpack_from("<I", data, 164)[0]
        replacement = b"icudt72l/nfc.nrm\0"
        data[name_start:name_start + len(replacement)] = replacement
        row = probe.inventory(data, "icudt72l")["members"]["nfc.nrm"]
        self.assertEqual(row, {"status": "last-entry-length-unknown", "offset": 416})
        self.assertNotIn("sha256", row)

    def test_all_declared_entries_are_checked(self):
        for offset, value in [(168, 0), (168, 2**32-1), (164, 0)]:
            data = fixture()
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset,value=value), self.assertRaises(ValueError):
                probe.inventory(data, "icudt72l")
        data = fixture()
        data[172] = 0xff
        with self.assertRaises(ValueError):
            probe.inventory(data, "icudt72l")
        with self.assertRaises(ValueError):
            probe.inventory(fixture(), "arbitrary-prefix")

    def test_storage_hash_includes_padding(self):
        data = fixture()
        original = probe.inventory(data, "icudt72l")["members"]["coll/en.res"]
        data[335] ^= 1
        changed = probe.inventory(data, "icudt72l")["members"]["coll/en.res"]
        self.assertNotEqual(original["sha256"], changed["sha256"])
        self.assertEqual(original["size"], changed["size"])

    def test_prefixes_and_mismatch(self):
        for prefix in ("icudt70l", "icudt72l", "icudt74l", "icudt76l"):
            data = fixture().replace(b"icudt72l", prefix.encode())
            self.assertEqual(probe.inventory(data, prefix)["prefixNameCount"], 3)
        with self.assertRaisesRegex(ValueError, "^prefix-mismatch$"):
            probe.inventory(fixture(), "icudt70l")

    def test_count_and_name_caps_independently(self):
        with patch.object(probe, "MAX_ENTRIES", 3):
            self.assertEqual(probe.inventory(fixture(), "icudt72l")["entryCount"], 3)
        with patch.object(probe, "MAX_ENTRIES", 2), self.assertRaises(ValueError):
            probe.inventory(fixture(), "icudt72l")
        # The longest fixture name is 22 bytes plus its terminating NUL.
        with patch.object(probe, "NAME_CAP", 23):
            probe.inventory(fixture(), "icudt72l")
        with patch.object(probe, "NAME_CAP", 22), self.assertRaises(ValueError):
            probe.inventory(fixture(), "icudt72l")

    def test_partial_prefix_count_requires_slash(self):
        data = fixture().replace(b"icudt72l/zzz", b"icudt72lzzzz")
        result = probe.inventory(data, "icudt72l")
        self.assertEqual(result["entryCount"], 3)
        self.assertEqual(result["prefixNameCount"], 2)

    def test_unselected_equal_offsets_rejected(self):
        data = fixture().replace(b"icudt72l/coll", b"icudt70l/coll")
        self.assertEqual(probe.inventory(data, "icudt72l")["prefixNameCount"], 1)
        struct.pack_into("<I", data, 160, 112)
        with self.assertRaises(ValueError):
            probe.inventory(data, "icudt72l")

    def test_order_flags_and_short_member_interval(self):
        for offset, kind, value in [(172,"B",31),(172,"B",127),(172,"B",ord('z')),
                                    (160,"I",112),(160,"I",135),(258,"B",0),
                                    (264,"B",1),(265,"B",1),(260,"H",19)]:
            data = fixture()
            struct.pack_into("<" + kind, data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                probe.inventory(data, "icudt72l")

    def test_resource_projection_and_en_us_selection(self):
        data = fixture()
        member = resource_fixture()
        data[256:336] = member
        delta = len(member) - 80
        struct.pack_into("<I", data, 160, 192 + delta)
        struct.pack_into("<I", data, 168, 272 + delta)
        # Use unused name-table space without shifting offsets.
        name = b"icudt72l/coll/en_US.res\0"
        data[230:230 + len(name)] = name
        struct.pack_into("<I", data, 148, 86)
        result = probe.inventory(data, "icudt72l")
        row = result["members"]["coll/en_US.res"]
        self.assertEqual(row["resource"]["status"], "observed-selected-fields")
        self.assertTrue(row["resource"]["defaultIsStandard"])
        self.assertEqual(row["sha256"], hashlib.sha256(member).hexdigest())
        self.assertEqual(result["members"]["coll/en.res"], {"status": "absent"})
        with patch.object(probe.icu_resource_probe, "MEMBER_CAP", len(member) - 1):
            limited = probe.inventory(data, "icudt72l")["members"]["coll/en_US.res"]
            self.assertEqual(limited["resource"], {"status": "unavailable", "reason": "limit"})
            self.assertEqual(limited["sha256"], row["sha256"])

    def test_final_resource_not_parsed(self):
        data = fixture().replace(b"icudt72l/coll", b"icudt70l/coll")
        name = b"icudt72l/coll/root.res\0"
        data[216:216 + len(name)] = name
        with patch.object(probe.icu_resource_probe, "project_resource", side_effect=AssertionError("must not parse")):
            row = probe.inventory(data, "icudt72l")["members"]["coll/root.res"]
        self.assertEqual(row, {"status": "last-entry-length-unknown", "offset": 416})

    def test_cap(self):
        data = fixture()
        data.extend(bytes(64 * 1024 * 1024 - len(data)))
        self.assertEqual(probe.inventory(data, "icudt72l")["entryCount"], 3)
        data.append(0)
        with self.assertRaisesRegex(ValueError, "^unsupported-package-layout$"):
            probe.inventory(data, "icudt72l")


if __name__ == "__main__":
    unittest.main()
