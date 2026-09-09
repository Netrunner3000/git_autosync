"""Last-synced lookups, including the pre-2026-09 basename keys."""
from app import repo_state


def test_entry_key_is_preferred(monkeypatch):
    monkeypatch.setattr(repo_state, "read_all",
                        lambda: {"sentinel_fork/vpn_agent": "2026-09-09 20:00:00",
                                 "vpn_agent": "2020-01-01 00:00:00"})
    assert repo_state.time_since_synced("sentinel_fork/vpn_agent") is not None
    assert repo_state.days_since_synced("sentinel_fork/vpn_agent") == 0


def test_falls_back_to_basename_for_old_state(monkeypatch):
    """State written before the engine reported config entries."""
    monkeypatch.setattr(repo_state, "read_all",
                        lambda: {"vpn_agent": "2026-09-09 20:00:00"})
    assert repo_state.time_since_synced("sentinel_fork/vpn_agent") is not None


def test_unknown_repo_is_never(monkeypatch):
    monkeypatch.setattr(repo_state, "read_all", lambda: {"other": "2026-09-09 20:00:00"})
    assert repo_state.time_since_synced("sentinel_fork/vpn_agent") is None
    assert repo_state.is_stale("sentinel_fork/vpn_agent") is True
