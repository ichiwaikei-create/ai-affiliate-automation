from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from automation_lib import (
    CONTENT_DIR,
    DATA_DIR,
    FORBIDDEN_PATTERNS,
    REQUIRED_AFFILIATE_FIELDS,
    REQUIRED_TOPIC_FIELDS,
    REQUIRED_TOPIC_TEMPLATE_FIELDS,
    SITE_DIR,
    extract_urls,
    load_all_topics,
    load_articles,
    load_yaml,
    parse_date,
    slugify,
    today_jst,
)


def fail(errors: List[str], message: str) -> None:
    errors.append(message)


def validate_catalog(errors: List[str]) -> Dict[str, Any]:
    catalog = load_yaml(DATA_DIR / "affiliate_catalog.yml")
    items = catalog.get("items", [])
    if not isinstance(items, list) or not items:
        fail(errors, "data/affiliate_catalog.yml must contain a non-empty items list")
        return catalog

    seen_ids = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            fail(errors, f"affiliate item #{index} must be a mapping")
            continue
        missing = REQUIRED_AFFILIATE_FIELDS - set(item)
        if missing:
            fail(errors, f"affiliate item {item.get('id', index)} missing fields: {sorted(missing)}")
        item_id = item.get("id")
        if item_id in seen_ids:
            fail(errors, f"duplicate affiliate id: {item_id}")
        seen_ids.add(item_id)
        if not isinstance(item.get("approved"), bool):
            fail(errors, f"affiliate item {item_id} approved must be true or false")
        if not str(item.get("official_url", "")).startswith("https://"):
            fail(errors, f"affiliate item {item_id} official_url must start with https://")

        checked = parse_date(item.get("last_checked"))
        if checked is None:
            fail(errors, f"affiliate item {item_id} last_checked must be YYYY-MM-DD")
        elif (today_jst() - checked).days > 180:
            fail(errors, f"affiliate item {item_id} last_checked is older than 180 days")

        if item.get("approved"):
            affiliate_url = str(item.get("affiliate_url", ""))
            pr_label = str(item.get("pr_label", ""))
            if not affiliate_url.startswith("https://"):
                fail(errors, f"approved affiliate item {item_id} requires https affiliate_url")
            if "example.com" in affiliate_url or "placeholder" in affiliate_url:
                fail(errors, f"approved affiliate item {item_id} contains placeholder affiliate_url")
            if not any(token in pr_label for token in ("PR", "広告", "アフィリエイト")):
                fail(errors, f"approved affiliate item {item_id} requires PR/ad disclosure in pr_label")
            if int(item.get("payout_yen", 0)) < 0:
                fail(errors, f"affiliate item {item_id} payout_yen cannot be negative")
    return catalog


def validate_topics(errors: List[str]) -> Dict[str, Any]:
    data = load_yaml(DATA_DIR / "topics.yml")
    site = data.get("site", {})
    if not site.get("title") or not site.get("description"):
        fail(errors, "data/topics.yml site.title and site.description are required")
    topics = data.get("topics", [])
    if not isinstance(topics, list) or not topics:
        fail(errors, "data/topics.yml must contain a non-empty topics list")
        return data
    ids = set()
    slugs = set()
    for topic in topics:
        missing = REQUIRED_TOPIC_FIELDS - set(topic)
        if missing:
            fail(errors, f"topic {topic.get('id', '?')} missing fields: {sorted(missing)}")
        if topic.get("id") in ids:
            fail(errors, f"duplicate topic id: {topic.get('id')}")
        if topic.get("slug") in slugs:
            fail(errors, f"duplicate topic slug: {topic.get('slug')}")
        ids.add(topic.get("id"))
        slugs.add(topic.get("slug"))
        if not isinstance(topic.get("pain_points"), list) or len(topic.get("pain_points", [])) < 2:
            fail(errors, f"topic {topic.get('id')} requires at least two pain_points")
        if not isinstance(topic.get("product_categories"), list):
            fail(errors, f"topic {topic.get('id')} product_categories must be a list")
    return data


def validate_topic_templates(errors: List[str]) -> None:
    path = DATA_DIR / "topic_templates.yml"
    if not path.exists():
        fail(errors, "data/topic_templates.yml is required to generate at least 100 SEO topics")
        return
    template_data = load_yaml(path)
    missing = REQUIRED_TOPIC_TEMPLATE_FIELDS - set(template_data)
    if missing:
        fail(errors, f"data/topic_templates.yml missing fields: {sorted(missing)}")
        return
    _, all_topics = load_all_topics()
    if len(all_topics) < 100:
        fail(errors, f"topic inventory must contain at least 100 topics; found {len(all_topics)}")
    ids = set()
    slugs = set()
    for topic in all_topics:
        missing_topic = REQUIRED_TOPIC_FIELDS - set(topic)
        if missing_topic:
            fail(errors, f"expanded topic {topic.get('id', '?')} missing fields: {sorted(missing_topic)}")
        if topic.get("id") in ids:
            fail(errors, f"duplicate expanded topic id: {topic.get('id')}")
        if topic.get("slug") in slugs:
            fail(errors, f"duplicate expanded topic slug: {topic.get('slug')}")
        ids.add(topic.get("id"))
        slugs.add(topic.get("slug"))


def validate_revenue_model(errors: List[str]) -> None:
    path = DATA_DIR / "revenue_model.yml"
    if not path.exists():
        fail(errors, "data/revenue_model.yml is required")
        return
    model = load_yaml(path)
    assumptions = model.get("assumptions", {})
    monthly_goal = int(model.get("monthly_goal_yen", 0))
    average_payout = int(assumptions.get("average_payout_yen", 0))
    click_rate = float(assumptions.get("click_through_rate", 0))
    conversion_rate = float(assumptions.get("conversion_rate", 0))
    if monthly_goal <= 0:
        fail(errors, "revenue_model monthly_goal_yen must be positive")
    if average_payout <= 0:
        fail(errors, "revenue_model average_payout_yen must be positive")
    if not 0 < click_rate <= 1:
        fail(errors, "revenue_model click_through_rate must be between 0 and 1")
    if not 0 < conversion_rate <= 1:
        fail(errors, "revenue_model conversion_rate must be between 0 and 1")


def validate_content(errors: List[str], catalog: Dict[str, Any]) -> None:
    if not CONTENT_DIR.exists():
        return
    approved_urls = {
        item["affiliate_url"]
        for item in catalog.get("items", [])
        if item.get("approved") and item.get("affiliate_url")
    }
    approved_go_paths = {
        f"/go/{slugify(str(item['id']))}.html"
        for item in catalog.get("items", [])
        if item.get("approved") and item.get("affiliate_url")
    }
    slugs = set()
    for article in load_articles():
        path = article["_path"]
        body = article["_body"]
        title = article.get("title")
        slug = article.get("slug")
        if not title or not slug:
            fail(errors, f"{path} requires title and slug frontmatter")
        if slug in slugs:
            fail(errors, f"duplicate article slug: {slug}")
        slugs.add(slug)
        if article.get("status") not in {"draft", "review", "published"}:
            fail(errors, f"{path} status must be draft, review, or published")
        if article.get("status") == "published" and len(body) < 900:
            fail(errors, f"{path} published body is too short for useful SEO content")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in body or pattern in str(title):
                fail(errors, f"{path} contains forbidden pattern: {pattern}")
        used_affiliate_urls = [url for url in approved_urls if url in body]
        if used_affiliate_urls:
            disclosure = str(article.get("monetization_disclosure", "")) + body
            if not any(token in disclosure for token in ("広告", "PR", "アフィリエイト")):
                fail(errors, f"{path} uses affiliate URLs without disclosure")
        for url in extract_urls(body):
            if "bit.ly" in url or "tinyurl.com" in url:
                fail(errors, f"{path} uses shortened URL: {url}")
        for go_path in set(re.findall(r"\]\((/go/[^)]+)\)", body)):
            if go_path not in approved_go_paths:
                fail(errors, f"{path} links to unapproved redirect path: {go_path}")


def validate_site(errors: List[str]) -> None:
    required = [
        SITE_DIR / "index.html",
        SITE_DIR / "articles" / "index.html",
        SITE_DIR / "sitemap.xml",
        SITE_DIR / "robots.txt",
        SITE_DIR / "assets" / "style.css",
    ]
    for path in required:
        if not path.exists():
            fail(errors, f"missing built site file: {path}")
    for path in SITE_DIR.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if "<title>" not in text or '<meta name="description"' not in text:
            fail(errors, f"{path} missing title or meta description")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                fail(errors, f"{path} contains forbidden pattern: {pattern}")
    go_dir = SITE_DIR / "go"
    if go_dir.exists():
        for path in go_dir.glob("*.html"):
            text = path.read_text(encoding="utf-8")
            if "rel=\"nofollow sponsored\"" not in text:
                fail(errors, f"{path} missing sponsored nofollow marker")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-site", action="store_true")
    args = parser.parse_args()

    errors: List[str] = []
    catalog = validate_catalog(errors)
    validate_topics(errors)
    validate_topic_templates(errors)
    validate_revenue_model(errors)
    validate_content(errors, catalog)
    if args.include_site:
        validate_site(errors)

    if errors:
        print("Quality check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Quality check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
