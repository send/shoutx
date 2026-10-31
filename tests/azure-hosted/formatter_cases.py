"""Finite public synthetic values; never execute rejected protocol-looking text."""


def values():
    return [
        ("ascii", "compile phase"),
        ("unicode", "日本語ไทยالعربيةदेवनागरी😀e\u0301"),
        ("escapes", "%0A%AZP25;]"),
        ("spaces", " \t label \t "),
        ("cap", "x" * 1_048_576),
    ]


def expected_blocks(debug):
    blocks = {}
    for name, value in values():
        blocks["SX_DEBUG_" + name] = ["##[debug]" + value] if debug else []
        blocks["SX_GROUP_" + name] = ["##[group]" + value, "SX_INSIDE_" + name,
                                     "##[endgroup]"]
    blocks["SX_DEBUG_empty"] = ["##[debug]"] if debug else []
    blocks["SX_NESTED"] = ["##[group]outer", "SX_OUTER", "##[group]inner",
                           "SX_INNER", "##[endgroup]", "SX_OUTER_AFTER_INNER",
                           "##[endgroup]"]
    return blocks
