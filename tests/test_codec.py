"""Tests for the DSIOT tree codec."""

from custom_components.daikin_india.dsiot.codec import (
    ascii_reversed,
    build_tree,
    flatten,
    le_int,
    le_uint,
    md_int,
    md_step,
    to_le_hex,
)


def test_flatten_and_build_round_trip() -> None:
    flat = {
        "dgc_status.e_1002.e_A002.p_01": "01",
        "dgc_status.e_1002.e_3001.p_01": "0200",
        "dgc_status.e_1002.e_3001.p_02": "2e",
    }
    tree = build_tree(flat)
    assert tree == {
        "pn": "dgc_status",
        "pch": [
            {
                "pn": "e_1002",
                "pch": [
                    {"pn": "e_A002", "pch": [{"pn": "p_01", "pv": "01"}]},
                    {
                        "pn": "e_3001",
                        "pch": [{"pn": "p_01", "pv": "0200"}, {"pn": "p_02", "pv": "2e"}],
                    },
                ],
            }
        ],
    }
    values, meta = flatten(tree)
    assert values == flat
    assert meta == {}


def test_flatten_keeps_metadata() -> None:
    values, meta = flatten(
        {"pn": "x", "pt": 1, "pch": [{"pn": "p_01", "pt": 3, "pv": "0200", "md": {"mx": "2F00"}}]}
    )
    assert values == {"x.p_01": "0200"}
    assert md_int(meta["x.p_01"], "mx") == 0x2F


def test_hex_helpers() -> None:
    assert le_uint("0200") == 2
    assert le_uint("0F0000") == 15
    assert le_uint(95) == 95
    assert le_uint("zz") is None
    assert le_int("FEFF") == -2
    assert le_int("2F00") == 47
    assert to_le_hex(2, 2) == "0200"
    assert to_le_hex(-2, 1) == "FE"
    assert to_le_hex(16, 3) == "100000"


def test_ascii_reversed() -> None:
    assert ascii_reversed("3455") == "U4"
    assert ascii_reversed("00") is None


def test_md_step() -> None:
    assert md_step({"st": 245}) == 0.5
    assert md_step({"st": "1"}) == 1
    assert md_step({"st": 0x15}) == 50
    assert md_step({}) is None
