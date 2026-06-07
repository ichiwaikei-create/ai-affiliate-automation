from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from automation_lib import load_all_topics  # noqa: E402


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_quality_check_passes() -> None:
    result = run_script("scripts/quality_check.py")
    assert "Quality check passed." in result.stdout


def test_site_build_outputs_required_files() -> None:
    run_script("scripts/build_site.py")
    required = [
        ROOT / "site" / "index.html",
        ROOT / "site" / "articles" / "index.html",
        ROOT / "site" / "sitemap.xml",
        ROOT / "site" / "robots.txt",
        ROOT / "site" / "assets" / "style.css",
    ]
    for path in required:
        assert path.exists(), f"missing {path}"


def test_quality_check_passes_with_site() -> None:
    run_script("scripts/build_site.py")
    result = run_script("scripts/quality_check.py", "--include-site")
    assert "Quality check passed." in result.stdout


def test_topic_inventory_supports_100_pages() -> None:
    _, topics = load_all_topics()
    assert len(topics) >= 100


def test_weekly_report_includes_revenue_reverse_math() -> None:
    run_script("scripts/weekly_report.py")
    reports = sorted((ROOT / "reports").glob("weekly-*.md"))
    assert reports
    text = reports[-1].read_text(encoding="utf-8")
    assert "月100万円への逆算" in text
    assert "必要検索流入" in text


def test_launch_audit_reports_current_blockers() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/launch_audit.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode in {0, 2}
    assert "Launch Audit" in result.stdout
    assert "Approved affiliate links" in result.stdout
