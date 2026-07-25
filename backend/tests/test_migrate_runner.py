"""
MIG1 (deep-review P8): the tracked migration runner's pure logic — natural
version ordering + pending calculation (no DB).
"""
from scripts.db.migrate import _sort_key, order_versions, pending_versions


def test_natural_sort_handles_numeric_and_suffix():
    names = ["074_admin_settings", "004b_update", "004_x", "065b_fix", "065_c", "10_a", "003_y"]
    ordered = order_versions(names)
    assert ordered == ["003_y", "004_x", "004b_update", "10_a", "065_c", "065b_fix", "074_admin_settings"]


def test_sort_key_shape():
    assert _sort_key("004b_update") == (4, "b_update")
    assert _sort_key("074_admin_settings") == (74, "_admin_settings")


def test_pending_excludes_applied_preserves_order():
    allv = ["003_a", "004_b", "005_c", "006_d"]
    applied = {"003_a", "005_c"}
    assert pending_versions(allv, applied) == ["004_b", "006_d"]


def test_pending_empty_when_all_applied():
    allv = ["003_a", "004_b"]
    assert pending_versions(allv, {"003_a", "004_b"}) == []
