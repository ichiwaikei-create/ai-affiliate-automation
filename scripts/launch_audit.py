from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List

from automation_lib import DATA_DIR, REPORTS_DIR, SITE_DIR, load_all_topics, load_articles, load_yaml, today_jst, write_text


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def git_remote() -> str:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def exists(path: Path) -> bool:
    return path.exists() and (not path.is_file() or path.stat().st_size >= 0)


def main() -> int:
    today = today_jst()
    catalog = load_yaml(DATA_DIR / "affiliate_catalog.yml")
    topics_data = load_yaml(DATA_DIR / "topics.yml")
    tracking = load_yaml(DATA_DIR / "tracking.yml")
    revenue_model = load_yaml(DATA_DIR / "revenue_model.yml")
    _, topics = load_all_topics()
    articles = load_articles()
    approved_items = [item for item in catalog.get("items", []) if item.get("approved")]
    analytics = tracking.get("analytics", {})
    remote = git_remote()
    published_articles = [article for article in articles if article.get("status") == "published"]
    assumptions = revenue_model.get("assumptions", {})
    target_pages = int(assumptions.get("published_pages_target", 100))
    base_url = topics_data.get("site", {}).get("base_url", "")

    checks: List[Check] = [
        Check("GitHub remote", bool(remote), remote or "origin remote is not configured"),
        Check("GitHub Actions", exists(Path(".github/workflows/daily_generate.yml")) and exists(Path(".github/workflows/deploy.yml")), "daily/deploy workflows present"),
        Check("GitHub Pages artifact", exists(SITE_DIR / "index.html") and exists(SITE_DIR / "sitemap.xml"), "site/index.html and sitemap.xml present"),
        Check("Production base_url", base_url.startswith("https://") and "example.com" not in base_url, base_url or "base_url is empty"),
        Check("Published articles", len(published_articles) >= target_pages, f"{len(published_articles)} published articles for {target_pages}-page target"),
        Check("100-page inventory", len(topics) >= target_pages, f"{len(topics)} topic candidates for {target_pages}-page target"),
        Check("Approved affiliate links", len(approved_items) > 0, f"{len(approved_items)} approved affiliate items"),
        Check("Analytics events", analytics.get("provider") in {"plausible", "google_analytics"}, f"provider={analytics.get('provider', 'none')}"),
    ]

    passed = [check for check in checks if check.passed]
    blockers = [check for check in checks if not check.passed]
    lines = [
        f"# Launch Audit — {today.isoformat()}",
        "",
        "## 結論",
        "",
        f"- passed: {len(passed)}/{len(checks)}",
        f"- blockers: {len(blockers)}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        mark = "OK" if check.passed else "BLOCKED"
        lines.append(f"- {mark}: {check.name} — {check.detail}")

    lines.extend(
        [
            "",
            "## Next Actions",
            "",
            "- GitHub remote が未設定なら、GitHubリポジトリを作成して `origin` を追加する。",
            "- 承認済みアフィリリンクが0件なら、A8.net・楽天・Amazonの提携URLを `data/affiliate_catalog.yml` に入れる。",
            "- 分析タグが未設定なら、`data/tracking.yml` にPlausibleまたはGoogle Analyticsを設定する。",
            "- 記事数が100未満なら、GitHub Actionsの日次生成を継続する。",
            "",
        ]
    )
    write_text(REPORTS_DIR / f"launch-audit-{today.isoformat()}.md", "\n".join(lines))
    print("\n".join(lines))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
