"""
Detector feature-flag resolution tests (pure logic, no DB).

Locks in the migration semantics: off skips, shadow/on pass through, and canary
resolves per account deterministically. The score-exclusion of shadow events is
covered structurally by the engine (alerts loop + total_delta + score queries all
filter on shadow); these tests guard the resolver those paths depend on.
"""
import uuid

from app.services.detector_flag_service import (
    DetectorFlagService,
    VALID_MODES,
    EFFECTIVE_ON,
    EFFECTIVE_OFF,
    EFFECTIVE_SHADOW,
)

svc = DetectorFlagService()


def test_valid_modes():
    assert VALID_MODES == {"off", "shadow", "canary", "on"}


def test_missing_detector_defaults_to_on():
    # Unknown detector, empty flag map → fail safe to live.
    assert svc.resolve("nope", uuid.uuid4(), {}) == EFFECTIVE_ON


def test_explicit_modes_pass_through():
    acct = uuid.uuid4()
    assert svc.resolve("d", acct, {"d": ("off", 100)}) == EFFECTIVE_OFF
    assert svc.resolve("d", acct, {"d": ("shadow", 100)}) == EFFECTIVE_SHADOW
    assert svc.resolve("d", acct, {"d": ("on", 100)}) == EFFECTIVE_ON


def test_canary_boundaries():
    acct = uuid.uuid4()
    # 0% → everyone dark; 100% → everyone live.
    assert svc.resolve("d", acct, {"d": ("canary", 0)}) == EFFECTIVE_SHADOW
    assert svc.resolve("d", acct, {"d": ("canary", 100)}) == EFFECTIVE_ON


def test_canary_is_deterministic_per_account():
    acct = uuid.uuid4()
    flags = {"d": ("canary", 50)}
    first = svc.resolve("d", acct, flags)
    # Same (detector, account) always resolves the same way — no flapping.
    for _ in range(20):
        assert svc.resolve("d", acct, flags) == first


def test_canary_bucket_spreads_accounts():
    # Across many accounts, a 50% canary should put roughly half live.
    flags = {"d": ("canary", 50)}
    live = sum(
        1 for _ in range(400)
        if svc.resolve("d", uuid.uuid4(), flags) == EFFECTIVE_ON
    )
    assert 120 < live < 280  # ~200 expected, generous bounds for hash spread


def test_bucket_is_in_range():
    for _ in range(100):
        b = DetectorFlagService._bucket("d", uuid.uuid4())
        assert 0 <= b < 100


def test_different_detectors_hash_independently():
    # Same account should not be correlated across detectors (different salt).
    acct = uuid.uuid4()
    buckets = {DetectorFlagService._bucket(f"det{i}", acct) for i in range(10)}
    assert len(buckets) > 1  # not all identical
