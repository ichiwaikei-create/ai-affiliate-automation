from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from automation_lib import (
    CONTENT_DIR,
    affiliate_go_url,
    approved_affiliate_items,
    build_frontmatter,
    load_all_topics,
    load_articles,
    load_yaml,
    DATA_DIR,
    today_jst,
    write_text,
)


def existing_topic_ids() -> set[str]:
    return {article.get("topic_id") for article in load_articles() if article.get("topic_id")}


def select_topics(topics: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    used = existing_topic_ids()
    candidates = [topic for topic in topics if topic["id"] not in used]
    candidates.sort(key=lambda t: int(t.get("priority", 999)))
    return candidates[:count]


def affiliate_section(catalog: Dict[str, Any], categories: List[str]) -> str:
    items = approved_affiliate_items(catalog, categories)
    if not items:
        return (
            "## 関連教材・ツール\n\n"
            "現時点では、提携条件を確認済みの広告リンクだけを掲載する方針です。"
            "未承認リンクや条件未確認の案件は公開しません。\n"
        )

    lines = [
        "## 関連教材・ツール",
        "",
        "以下には広告リンクが含まれます。掲載前に提携条件とPR表記を確認しています。",
        "",
    ]
    for item in items[:3]:
        lines.extend(
            [
                f"### {item['name']}",
                f"- 種別: {item['category']}",
                f"- 提供元: {item['provider']}",
                f"- {item['pr_label']}",
                f"- リンク: [{item['name']}]({affiliate_go_url(item)})",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_article(topic: Dict[str, Any], catalog: Dict[str, Any]) -> str:
    today = today_jst().isoformat()
    title = topic["title"]
    keyword = topic["keyword"]
    pain_points = topic.get("pain_points", [])
    categories = topic.get("product_categories", [])

    meta = {
        "title": title,
        "slug": topic["slug"],
        "topic_id": topic["id"],
        "keyword": keyword,
        "audience": topic["audience"],
        "status": "published",
        "review_status": "auto_quality_checked",
        "generated_at": today,
        "updated_at": today,
        "description": f"{keyword}で調べる人向けに、導入前の判断基準、失敗しやすい点、現実的な進め方を整理します。",
        "monetization_disclosure": "この記事には広告リンクが含まれる場合があります。未承認リンクは掲載しません。",
    }

    pain_list = "\n".join(f"- {point}" for point in pain_points)
    checklist = "\n".join(
        [
            "- 何の業務を短縮したいかを1つに絞る",
            "- 入力情報の置き場を1つに決める",
            "- 現場の責任者と確認頻度を決める",
            "- AIが間違えた場合の確認手順を残す",
            "- 成果指標を時間、件数、金額のどれで見るか決める",
        ]
    )
    body = f"""# {title}

## 先に結論

{keyword}で調べている段階では、最初にツール名を決めるより、対象業務と情報の置き場を決める方が重要です。AI導入は魔法の自動化ではなく、繰り返し業務を小さく切って、入力と確認を整える作業です。

## 想定読者

この記事は、{topic['audience']}に向けて書いています。検索意図は「{topic['search_intent']}」です。

## よくある詰まり

{pain_list}

## 判断基準

{topic['angle']} 判断の順番は次の通りです。

{checklist}

## 小さく始める例

最初の1週間で狙うべきことは、売上を直接伸ばすことではありません。議事録、問い合わせ整理、日報要約、社内マニュアル検索など、毎週必ず発生する作業を1つ選びます。その作業で「人間が判断する部分」と「AIに任せる部分」を分けます。

この分解をせずにAIツールを入れると、現場は何を任せてよいか分からず、結局いつもの手作業に戻ります。逆に、対象業務が1つなら失敗理由も記録しやすく、次の改善につながります。

## 限界と注意点

AIは入力された情報以上の判断はできません。古いマニュアル、担当者ごとに違うルール、未整理のチャット履歴をそのまま渡しても、安定した成果は出にくいです。また、顧客情報や社内機密を扱う場合は、利用規約、権限、保存先の確認が必要です。

{affiliate_section(catalog, categories)}

## 90日で見る指標

- 公開記事数: 100ページ
- 月間検索流入: 1,000以上
- アフィリクリック: 50以上
- 初成果: 1件以上

数字が出ない場合は、記事数を増やす前に検索テーマ、案件単価、読者の課題を見直します。
"""
    return build_frontmatter(meta) + "\n" + body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    _, topics = load_all_topics()
    catalog = load_yaml(DATA_DIR / "affiliate_catalog.yml")
    selected = select_topics(topics, args.count)
    if not selected:
        print("No unused topics left. Add topics to data/topics.yml or data/topic_templates.yml.")
        return 0

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    for topic in selected:
        path = CONTENT_DIR / f"{topic['slug']}.md"
        if path.exists():
            continue
        write_text(path, build_article(topic, catalog))
        print(f"generated {Path(path).relative_to(CONTENT_DIR.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
