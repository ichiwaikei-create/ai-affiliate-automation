from __future__ import annotations

import math
from collections import Counter

from automation_lib import (
    DATA_DIR,
    REPORTS_DIR,
    SITE_DIR,
    extract_urls,
    load_all_topics,
    load_articles,
    load_yaml,
    today_jst,
    write_text,
)


def count_site_urls() -> int:
    if not SITE_DIR.exists():
        return 0
    urls = set()
    for path in SITE_DIR.rglob("*.html"):
        urls.update(extract_urls(path.read_text(encoding="utf-8")))
    return len(urls)


def main() -> int:
    today = today_jst()
    catalog = load_yaml(DATA_DIR / "affiliate_catalog.yml")
    metrics = load_yaml(DATA_DIR / "manual_metrics.yml")
    revenue_model = load_yaml(DATA_DIR / "revenue_model.yml")
    _, all_topics = load_all_topics()
    articles = load_articles()
    statuses = Counter(article.get("status", "unknown") for article in articles)
    approved_items = [item for item in catalog.get("items", []) if item.get("approved")]
    pending_items = [item for item in catalog.get("items", []) if not item.get("approved")]
    categories = Counter(item.get("category", "unknown") for item in approved_items)

    assumptions = revenue_model.get("assumptions", {})
    monthly_goal = int(revenue_model.get("monthly_goal_yen", 1000000))
    average_payout = int(assumptions.get("average_payout_yen", 5000))
    click_rate = float(assumptions.get("click_through_rate", 0.02))
    conversion_rate = float(assumptions.get("conversion_rate", 0.02))
    target_pages = int(assumptions.get("published_pages_target", 100))
    target_sessions = int(assumptions.get("monthly_search_sessions_target", 1000))
    target_clicks = int(assumptions.get("affiliate_clicks_target", 50))
    target_conversions = int(assumptions.get("conversions_target", 1))
    required_conversions = math.ceil(monthly_goal / average_payout)
    required_clicks = math.ceil(required_conversions / conversion_rate)
    required_sessions = math.ceil(required_clicks / click_rate)
    published_count = statuses.get("published", 0)
    search_sessions = int(metrics.get("search_sessions", 0))
    clicks = int(metrics.get("affiliate_clicks", 0))
    conversions = int(metrics.get("conversions", 0))

    report = f"""# Weekly Review — {today.isoformat()}

## 結論

- 公開記事: {published_count}/{target_pages}
- 検索流入: {search_sessions}/{target_sessions}
- アフィリクリック: {clicks}/{target_clicks}
- 初成果: {conversions}/{target_conversions}
- 推定売上: {int(metrics.get('revenue_yen', 0)):,}円

## 月100万円への逆算

- 月間目標: {monthly_goal:,}円
- 平均成果報酬: {average_payout:,}円
- 必要成約数: {required_conversions:,}件/月
- 想定CVR {conversion_rate:.1%} の必要クリック: {required_clicks:,}クリック/月
- 想定CTR {click_rate:.1%} の必要検索流入: {required_sessions:,}セッション/月
- 現在の不足検索流入: {max(required_sessions - search_sessions, 0):,}セッション/月

## コンテンツ

- published: {statuses.get('published', 0)}
- review: {statuses.get('review', 0)}
- draft: {statuses.get('draft', 0)}
- 生成候補トピック: {len(all_topics)}
- 残り候補トピック: {max(len(all_topics) - len(articles), 0)}
- site内外部URL数: {count_site_urls()}

## アフィリ案件

- 承認済み: {len(approved_items)}
- 未承認・確認待ち: {len(pending_items)}
- 承認済みカテゴリ: {dict(categories)}

## 次の手動確認

- A8.net、楽天、Amazonの提携承認状況を確認し、承認済み案件だけ `approved: true` にする。
- Search ConsoleとASP管理画面の数値を `data/manual_metrics.yml` に転記する。
- 90日で初成果がない場合、記事数ではなく検索テーマと案件単価を見直す。

## メモ

{metrics.get('notes', '')}
"""
    path = REPORTS_DIR / f"weekly-{today.isoformat()}.md"
    write_text(path, report)
    print(f"wrote {path.relative_to(REPORTS_DIR.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
