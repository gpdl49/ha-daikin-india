"""Encoding helpers for the DSIOT property tree.

Responses carry nested ``{"pn": name, "pch": [...]}`` containers with
``{"pn": name, "pv": value, "md": {...}}`` leaves. We flatten them to dotted
keys such as ``dgc_status.e_1002.e_3001.p_01`` and build writes the same way
in reverse. Multi-byte hex values are little-endian.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def flatten(
    node: Any,
    prefix: str = "",
    values: dict[str, Any] | None = None,
    meta: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Flatten a property tree into ``(values, metadata)`` keyed by dotted path."""
    values = {} if values is None else values
    meta = {} if meta is None else meta
    if not isinstance(node, dict):
        return values, meta
    name = node.get("pn")
    key = f"{prefix}.{name}" if prefix and name else (name or prefix)
    children = node.get("pch")
    if isinstance(children, list):
        for child in children:
            flatten(child, key, values, meta)
    elif "pv" in node and key:
        values[key] = node["pv"]
        if isinstance(node.get("md"), dict):
            meta[key] = node["md"]
    return values, meta


def build_tree(flat: Mapping[str, Any]) -> dict[str, Any]:
    """Build a ``pc`` write tree from dotted keys that share a single root."""
    root: dict[str, Any] = {}
    for key, value in flat.items():
        node = root
        *parents, leaf = key.split(".")
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    if len(root) != 1:
        raise ValueError(f"Write keys must share one root, got {sorted(root)}")
    ((name, body),) = root.items()
    return _to_pc(name, body)


def _to_pc(name: str, body: Any) -> dict[str, Any]:
    if isinstance(body, dict):
        return {"pn": name, "pch": [_to_pc(k, v) for k, v in body.items()]}
    return {"pn": name, "pv": body}


def le_uint(pv: Any) -> int | None:
    """Decode a little-endian hex string (or pass through an int)."""
    if isinstance(pv, bool):
        return int(pv)
    if isinstance(pv, int):
        return pv
    if not isinstance(pv, str) or not pv or len(pv) % 2:
        return None
    try:
        return int.from_bytes(bytes.fromhex(pv), "little")
    except ValueError:
        return None


def le_int(pv: Any) -> int | None:
    """Decode a signed little-endian hex string."""
    if isinstance(pv, int) and not isinstance(pv, bool):
        return pv
    if not isinstance(pv, str) or not pv or len(pv) % 2:
        return None
    try:
        return int.from_bytes(bytes.fromhex(pv), "little", signed=True)
    except ValueError:
        return None


def to_le_hex(value: int, nbytes: int) -> str:
    """Encode an integer as uppercase little-endian hex of ``nbytes`` bytes."""
    return value.to_bytes(nbytes, "little", signed=value < 0).hex().upper()


def ascii_reversed(pv: Any) -> str | None:
    """Decode a byte-reversed ASCII string (model names, error codes)."""
    if not isinstance(pv, str) or not pv or len(pv) % 2:
        return None
    try:
        raw = bytes.fromhex(pv)[::-1]
    except ValueError:
        return None
    text = raw.replace(b"\x00", b"").decode("ascii", errors="ignore").strip()
    return text or None


def md_int(md: Mapping[str, Any] | None, field: str) -> int | None:
    """Read an integer metadata field (``mi``/``mx``); hex values are little-endian."""
    if not md or field not in md:
        return None
    return le_uint(md[field])


def md_step(md: Mapping[str, Any] | None) -> float | None:
    """Decode ``md.st``: low nibble is the mantissa, high nibble the exponent."""
    if not md or "st" not in md:
        return None
    try:
        st = int(md["st"])
    except (TypeError, ValueError):
        return None
    exponent, mantissa = (st >> 4) & 0xF, st & 0xF
    scale = 10.0**exponent if exponent < 8 else 10.0 ** -(16 - exponent)
    return mantissa * scale
