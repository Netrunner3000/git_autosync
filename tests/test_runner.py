from app.runner import parse_summary

SAMPLE = """\
2026-06-27 02:00:00 | === git_autosync start (dry-run=0) ===
2026-06-27 02:00:00 | gitleaks: 8.18.0
---------------------------------------------
2026-06-27 02:00:00 | REPO: backup_manager  (/Users/as/Documents/lab/active/backup_manager)
2026-06-27 02:00:00 |   scanning for secrets...
2026-06-27 02:00:01 |   clean .
2026-06-27 02:00:01 |   committed changes.
2026-06-27 02:00:02 |   pushed to origin/main.
---------------------------------------------
2026-06-27 02:00:02 | REPO: sentinel_ai  (/Users/as/Documents/lab/active/sentinel_ai)
2026-06-27 02:00:02 |   scanning for secrets...
Finding:     ...REDACTED...
Secret:      REDACTED
RuleID:      aws-access-token
Entropy:     3.884184
File:        config/secrets.txt
Line:        2
Fingerprint: config/secrets.txt:aws-access-token:2

2026-06-27 02:00:02 |   BLOCKED: gitleaks found a secret in your changes. Nothing committed or pushed.
---------------------------------------------
2026-06-27 02:00:03 | REPO: vpn_agent  (/Users/as/Documents/lab/active/vpn_agent)
2026-06-27 02:00:03 |   SKIP: no 'origin' remote (run the GitHub setup script first)
---------------------------------------------
2026-06-27 02:00:03 | SUMMARY:
2026-06-27 02:00:03 |    SYNCED  backup_manager
2026-06-27 02:00:03 |    BLOCKED sentinel_ai  (secret in changes - see log)
2026-06-27 02:00:03 |    SKIP    vpn_agent  (no GitHub remote)
2026-06-27 02:00:03 | synced=1 blocked=1 skipped=1 errors=0 noop=0
2026-06-27 02:00:03 | === git_autosync end ===
"""


def test_parses_per_repo_statuses():
    result = parse_summary(SAMPLE)
    repos = result["repos"]
    assert repos["backup_manager"]["status"] == "SYNCED"
    assert repos["sentinel_ai"]["status"] == "BLOCKED"
    assert repos["sentinel_ai"]["detail"] == "secret in changes - see log"
    assert repos["vpn_agent"]["status"] == "SKIP"
    assert repos["vpn_agent"]["detail"] == "no GitHub remote"


def test_parses_counts():
    result = parse_summary(SAMPLE)
    assert result["counts"] == {
        "synced": 1,
        "blocked": 1,
        "skipped": 1,
        "errors": 0,
        "noop": 0,
    }


def test_ignores_pre_summary_repo_mentions():
    # "REPO: sentinel_ai" before SUMMARY: must not be mistaken for a status line.
    result = parse_summary(SAMPLE)
    assert len(result["repos"]) == 3


def test_handles_dry_run_ok_status():
    text = (
        "2026-06-27 02:00:00 | SUMMARY:\n"
        "2026-06-27 02:00:00 |    OK      backup_manager  (dry-run: would sync)\n"
        "2026-06-27 02:00:00 | synced=0 blocked=0 skipped=0 errors=0 noop=1\n"
    )
    result = parse_summary(text)
    assert result["repos"]["backup_manager"]["status"] == "OK"
    assert result["counts"]["noop"] == 1


def test_no_summary_returns_empty():
    result = parse_summary("nothing relevant here")
    assert result["repos"] == {}
    assert result["counts"] is None


def test_extracts_finding_for_blocked_repo():
    result = parse_summary(SAMPLE)
    findings = result["findings"]
    assert findings["sentinel_ai"] == {"file": "config/secrets.txt", "rule": "aws-access-token"}
    assert "backup_manager" not in findings


def test_finding_extraction_handles_either_field_order():
    # gitleaks --verbose prints RuleID: before File:; confirm the reverse
    # order is handled too rather than assuming a fixed sequence.
    text = (
        "REPO: myrepo  (/x/myrepo)\n"
        "File:        a.txt\n"
        "RuleID:      generic-api-key\n"
        "SUMMARY:\n"
        "   BLOCKED myrepo  (secret in changes - see log)\n"
    )
    result = parse_summary(text)
    assert result["findings"]["myrepo"] == {"file": "a.txt", "rule": "generic-api-key"}
