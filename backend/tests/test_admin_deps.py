"""Tests for admin IP-allowlist + proxy-trust helpers (admin auth hardening).

These guard the `_check_ip` / `_get_client_ip` logic added in the security pass: an
X-Forwarded-For header must NOT bypass the allowlist unless the app is explicitly told it
sits behind a trusted proxy (ADMIN_TRUST_PROXY_HEADERS).
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.api.admin.deps import _parse_allowlist, _get_client_ip, _check_ip


def _req(xff=None, host="1.2.3.4"):
    headers = {}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_parse_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_IP_ALLOWLIST", "  1.2.3.4, 10.0.0.0/8 ,")
    assert _parse_allowlist() == ["1.2.3.4", "10.0.0.0/8"]
    monkeypatch.setattr(settings, "ADMIN_IP_ALLOWLIST", None)
    assert _parse_allowlist() == []


def test_client_ip_ignores_xff_when_proxy_untrusted(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TRUST_PROXY_HEADERS", False)
    # spoofed header must be ignored — real socket peer wins
    assert _get_client_ip(_req(xff="9.9.9.9", host="1.2.3.4")) == "1.2.3.4"


def test_client_ip_honours_xff_when_proxy_trusted(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TRUST_PROXY_HEADERS", True)
    assert _get_client_ip(_req(xff="9.9.9.9, 10.0.0.1", host="1.2.3.4")) == "9.9.9.9"


def test_check_ip_noop_when_allowlist_empty(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_IP_ALLOWLIST", None)
    _check_ip(_req(host="8.8.8.8"))  # no raise


def test_check_ip_allows_exact_and_cidr(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_IP_ALLOWLIST", "1.2.3.4, 10.0.0.0/8")
    monkeypatch.setattr(settings, "ADMIN_TRUST_PROXY_HEADERS", False)
    _check_ip(_req(host="1.2.3.4"))     # exact
    _check_ip(_req(host="10.5.6.7"))    # inside CIDR


def test_check_ip_blocks_ip_not_in_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_IP_ALLOWLIST", "1.2.3.4")
    monkeypatch.setattr(settings, "ADMIN_TRUST_PROXY_HEADERS", False)
    with pytest.raises(HTTPException) as e:
        _check_ip(_req(host="9.9.9.9"))
    assert e.value.status_code == 404


def test_check_ip_spoofed_xff_cannot_bypass_when_untrusted(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_IP_ALLOWLIST", "1.2.3.4")
    monkeypatch.setattr(settings, "ADMIN_TRUST_PROXY_HEADERS", False)
    # attacker on 9.9.9.9 spoofs an allowlisted IP in the header — must still be blocked
    with pytest.raises(HTTPException) as e:
        _check_ip(_req(xff="1.2.3.4", host="9.9.9.9"))
    assert e.value.status_code == 404
