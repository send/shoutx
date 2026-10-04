import struct
import unittest

from icu_resource_probe import Resource
import icu_resource_probe as probe
from unittest.mock import patch


def fixture():
    data = bytearray(176)
    struct.pack_into("<H2sHH4B", data, 0, 32, b"\xda\x27", 20, 0, 0, 0, 2, 0)
    data[12:20] = b"ResB\2\0\0\0"
    base = 32
    struct.pack_into("<I7I", data, base, (2 << 28) | 32, 7, 15, 35, 35, 2, 0, 24)
    data[base+32:base+43] = b"collations\0"
    data[base+43:base+51] = b"default\0"
    data[base+51:base+60] = b"standard\0"
    data[base+62:base+80] = "standard\0".encode("utf-16-le")
    struct.pack_into("<4H2I", data, base+100, 2, 43, 51, 0, (6 << 28) | 1, 2 << 28)
    struct.pack_into("<2HI", data, base+128, 1, 32, (2 << 28) | 25)
    return data


class ResourceTests(unittest.TestCase):
    def test_selected_projection(self):
        self.assertEqual(Resource(fixture()).projection(), {
            "attributes": 0, "rootType": 2, "rootOffsetZero": False,
            "aliasPresent": False, "parentPresent": False, "parentIsRootPresent": False,
            "collationsPresent": True, "defaultPresent": True,
            "standardPresent": True, "defaultIsStandard": True, "standardType": 2})

    def test_empty_root(self):
        data = fixture()
        struct.pack_into("<I", data, 32, 2 << 28)
        self.assertEqual(Resource(data).projection(), {
            "attributes": 0, "rootType": 2, "rootOffsetZero": True, "collationsPresent": False,
            "aliasPresent": False, "parentPresent": False, "parentIsRootPresent": False})

    def test_bounds_and_unsupported_inputs(self):
        for offset, fmt, value in [(2,"B",0),(4,"H",19),(4,"H",29),(8,"B",1),(16,"B",3),
                                   (36,"I",8),(56,"I",4),(40,"I",10000),
                                   (160,"H",65535),(164,"I",(3<<28)|25),
                                   (142,"H",0xffff),(94,"H",0xdc00)]:
            data = fixture()
            struct.pack_into("<"+fmt, data, offset, value)
            with self.subTest(offset=offset,value=value), self.assertRaises(ValueError):
                Resource(data).projection()

    def test_default_compared_not_exported(self):
        data = fixture()
        struct.pack_into("<H", data, 94, ord('x'))
        result = Resource(data).projection()
        self.assertFalse(result["defaultIsStandard"])
        self.assertNotIn("x", str(result))

    def test_table32_root_and_collations(self):
        data = fixture()
        # Fit two table32 pairs in the same reserved interval.
        struct.pack_into("<5I", data, 132, 2, 43, 51, (6 << 28) | 1, 2 << 28)
        struct.pack_into("<3I", data, 160, 1, 32, (4 << 28) | 25)
        struct.pack_into("<I", data, 32, (4 << 28) | 32)
        result = Resource(data).projection()
        self.assertEqual(result["rootType"], 4)
        self.assertTrue(result["defaultIsStandard"])

    def test_key_order_and_string_termination(self):
        for offset, fmt, value in [(136,"H",43),(136,"H",32),(162,"H",0),
                                   (162,"H",60),(140,"I",(6<<28)|100),
                                   (64,"B",31)]:
            data = fixture()
            struct.pack_into("<"+fmt, data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                Resource(data).projection()
        data = fixture()
        data[94:128] = b"a\0" * 17
        with self.assertRaises(ValueError):
            Resource(data).projection()

    def test_header_short_input_and_bundle_slack(self):
        for data in (b"", fixture()[:50], fixture()[:160], fixture() + bytes(16)):
            with self.assertRaises(ValueError):
                Resource(data).projection()

    def test_empty_default_and_missing_default_are_distinct(self):
        data = fixture()
        struct.pack_into("<I", data, 140, 6 << 28)
        result = Resource(data).projection()
        self.assertTrue(result["defaultPresent"])
        self.assertFalse(result["defaultIsStandard"])
        data = fixture()
        data[75:82] = b"aaaaaaa"
        result = Resource(data).projection()
        self.assertFalse(result["defaultPresent"])
        self.assertNotIn("defaultIsStandard", result)

    def test_closed_projection_and_member_cap(self):
        result = probe.project_resource(fixture())
        self.assertEqual(set(result), {"status", "attributes", "rootType", "rootOffsetZero",
                                      "aliasPresent", "parentPresent", "parentIsRootPresent",
                                      "collationsPresent", "defaultPresent", "standardPresent",
                                      "defaultIsStandard", "standardType"})
        with patch.object(probe, "MEMBER_CAP", len(fixture())):
            self.assertEqual(probe.project_resource(fixture()), result)
        with patch.object(probe, "MEMBER_CAP", len(fixture()) - 1):
            self.assertEqual(probe.project_resource(fixture()),
                             {"status": "unavailable", "reason": "limit"})
        with patch.object(Resource, "projection", side_effect=ValueError("PRIVATE")):
            self.assertEqual(probe.project_resource(fixture()),
                             {"status": "unavailable", "reason": "layout"})

    def test_traversal_caps_independently(self):
        for name, accepted, rejected in [("TABLE_CAP", 2, 1), ("KEY_CAP", 11, 10),
                                          ("STRING_CAP", 9, 8)]:
            with self.subTest(name=name), patch.object(probe, name, accepted):
                self.assertEqual(probe.project_resource(fixture())["status"], "observed-selected-fields")
            with self.subTest(name=name), patch.object(probe, name, rejected):
                self.assertEqual(probe.project_resource(fixture()),
                                 {"status": "unavailable", "reason": "limit" if name != "KEY_CAP" else "layout"})

    def test_native_empty_string_encoding_and_alias_type(self):
        data = fixture()
        struct.pack_into("<I", data, 140, 0)
        result = Resource(data).projection()
        self.assertTrue(result["defaultPresent"])
        self.assertFalse(result["defaultIsStandard"])
        struct.pack_into("<I", data, 144, 3 << 28)
        self.assertEqual(Resource(data).projection()["standardType"], 3)

    def test_reason_categories_and_struct_errors(self):
        for offset, value, reason in [(16,3,"format-version"),(36,8,"pool-or-index-layout"),
                                      (56,4,"pool-or-index-layout"),(32,5<<28,"container-type"),
                                      (140,3<<28,"string-encoding")]:
            data = fixture()
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset):
                self.assertEqual(probe.project_resource(data), {"status":"unavailable","reason":reason})
        for kind in (3, 5):
            data = fixture()
            struct.pack_into("<I", data, 164, (kind << 28) | 25)
            self.assertEqual(probe.project_resource(data), {"status":"unavailable","reason":"container-type"})
        for error in (struct.error("PRIVATE"), probe.UnsupportedResource("PRIVATE")):
            with patch.object(Resource, "projection", side_effect=error):
                self.assertEqual(probe.project_resource(fixture()), {"status":"unavailable","reason":"layout"})

    def test_attributes_missing_fields_and_slack(self):
        data = fixture()
        struct.pack_into("<I", data, 56, 1)
        self.assertEqual(Resource(data).projection()["attributes"], 1)
        data[64:74] = b"aaaaaaaaaa"
        self.assertFalse(Resource(data).projection()["collationsPresent"])
        data = fixture()
        data[83:91] = b"zzzzzzzz"
        self.assertFalse(Resource(data).projection()["standardPresent"])
        self.assertEqual(probe.project_resource(fixture() + bytes(11))["status"], "observed-selected-fields")
        self.assertEqual(probe.project_resource(fixture() + bytes(12))["reason"], "layout")

    def test_index_relations_and_resources_top(self):
        for offset, value in [(40,7),(40,25),(60,36),(44,36),(48,37),(44,33)]:
            data = fixture()
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset,value=value), self.assertRaises(ValueError):
                Resource(data).projection()

    def test_redirect_key_presence_without_value_resolution(self):
        # A distinct bundle with three sorted root keys and opaque values.
        # Includes word zero: presence must not depend on handle truthiness.
        fields = ("aliasPresent", "parentPresent", "parentIsRootPresent")
        for kind in (2, 4):
            for mask in range(8):
                with self.subTest(kind=kind, mask=mask):
                    data = bytearray(176)
                    data[:32] = fixture()[:32]
                    keys = b"%%ALIAS\0%%Parent\0%%ParentIsRoot\0"
                    data[64:64+len(keys)] = keys
                    struct.pack_into("<I7I", data, 32, (kind << 28) | 24,
                                     7, 16, 36, 36, 3, 0, 16)
                    pairs = [(key, value) for i, (key, value) in enumerate(
                        [(32, 0), (40, 0x3fffffff), (49, 0xffffffff)]) if mask & (1 << i)]
                    count = len(pairs)
                    width, code = (2, "H") if kind == 2 else (4, "I")
                    struct.pack_into("<" + code * (count + 1), data, 128,
                                     count, *(key for key, _ in pairs))
                    values = (128 + width * (count + 1) + 3) & ~3
                    struct.pack_into("<" + "I" * count, data, values,
                                     *(value for _, value in pairs))
                    self.assertEqual(probe.project_resource(data), {
                        "status": "observed-selected-fields", "attributes": 0,
                        "rootType": kind, "rootOffsetZero": False,
                        "collationsPresent": False,
                        **{field: bool(mask & (1 << i)) for i, field in enumerate(fields)}})
if __name__ == "__main__":
    unittest.main()
