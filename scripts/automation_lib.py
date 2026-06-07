from __future__ import annotations

import datetime as dt
import html
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONTENT_DIR = ROOT / "content"
SITE_DIR = ROOT / "site"
REPORTS_DIR = ROOT / "reports"
GO_DIR_NAME = "go"

FORBIDDEN_PATTERNS = [
    "必ず稼げる",
    "誰でも稼げる",
    "誰でも月100万",
    "初心者でも簡単に稼げる",
    "AIだけで簡単",
    "AIがあれば全部解決",
    "完全放置で確実",
    "絶対に成果",
]

REQUIRED_AFFILIATE_FIELDS = {
    "id",
    "name",
    "category",
    "provider",
    "official_url",
    "affiliate_url",
    "payout_yen",
    "pr_label",
    "last_checked",
    "approved",
}

REQUIRED_TOPIC_FIELDS = {
    "id",
    "slug",
    "title",
    "keyword",
    "audience",
    "search_intent",
    "priority",
    "product_categories",
    "pain_points",
    "angle",
}


REQUIRED_TOPIC_TEMPLATE_FIELDS = {
    "industries",
    "use_cases",
    "tools",
}


def today_jst() -> dt.date:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    normalized = re.sub(r"[^a-z0-9\u3040-\u30ff\u3400-\u9fff]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized[:80] or "article"


def split_frontmatter(markdown: str) -> Tuple[Dict[str, Any], str]:
    if not markdown.startswith("---\n"):
        return {}, markdown
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return {}, markdown
    raw = markdown[4:end]
    body = markdown[end + 5 :]
    meta = yaml.safe_load(raw) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


def build_frontmatter(meta: Dict[str, Any]) -> str:
    raw = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{raw}\n---\n"


def load_articles() -> List[Dict[str, Any]]:
    articles: List[Dict[str, Any]] = []
    for path in sorted(CONTENT_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = split_frontmatter(raw)
        meta["_path"] = path
        meta["_body"] = body
        articles.append(meta)
    return articles


def approved_affiliate_items(catalog: Dict[str, Any], categories: Iterable[str] | None = None) -> List[Dict[str, Any]]:
    wanted = set(categories or [])
    items = []
    for item in catalog.get("items", []):
        if not item.get("approved"):
            continue
        if wanted and item.get("category") not in wanted:
            continue
        items.append(item)
    return items


def affiliate_go_url(item: Dict[str, Any]) -> str:
    return f"/{GO_DIR_NAME}/{slugify(str(item['id']))}.html"


def expand_template_topics(template_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build deterministic long-tail SEO topics from industry/use-case/tool axes."""
    missing = REQUIRED_TOPIC_TEMPLATE_FIELDS - set(template_data)
    if missing:
        raise ValueError(f"topic template missing fields: {sorted(missing)}")

    defaults = template_data.get("defaults", {})
    max_topics = int(template_data.get("max_generated_topics", 120))
    topics: List[Dict[str, Any]] = []
    priority = int(defaults.get("priority_start", 1000))

    for industry in template_data.get("industries", []):
        for use_case in template_data.get("use_cases", []):
            for tool in template_data.get("tools", []):
                if len(topics) >= max_topics:
                    return topics
                topic_id = f"auto_{industry['id']}_{use_case['id']}_{tool['id']}"
                title = f"{industry['name']}が{tool['name']}で{use_case['name']}を効率化する前に決めること"
                keyword = f"{industry['keyword']} {use_case['keyword']} {tool['keyword']}"
                topics.append(
                    {
                        "id": topic_id,
                        "slug": slugify(topic_id),
                        "title": title,
                        "keyword": keyword,
                        "audience": industry.get("audience", defaults.get("audience", "中小企業の社長・担当者")),
                        "search_intent": f"{industry['name']}で{use_case['name']}に{tool['name']}を使う前の判断基準を知りたい",
                        "priority": priority,
                        "product_categories": use_case.get(
                            "product_categories",
                            defaults.get("product_categories", ["course", "book", "tool"]),
                        ),
                        "pain_points": use_case.get("pain_points", defaults.get("pain_points", [])),
                        "angle": f"{industry['name']}では、{use_case['angle']} {tool['name']}は導入先ではなく、対象業務を決めた後の実行手段として扱う。",
                        "industry_name": industry["name"],
                        "use_case_name": use_case["name"],
                        "tool_name": tool["name"],
                        "industry_context": industry.get("context", ""),
                        "use_case_angle": use_case["angle"],
                        "tool_caution": tool.get("caution", ""),
                        "tool_strength": tool.get("strength", ""),
                        "generated_from_template": True,
                    }
                )
                priority += 1
    return topics


def load_all_topics() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    topics_data = load_yaml(DATA_DIR / "topics.yml")
    topics = list(topics_data.get("topics", []))
    template_path = DATA_DIR / "topic_templates.yml"
    if template_path.exists():
        topics.extend(expand_template_topics(load_yaml(template_path)))
    return topics_data, topics


def article_output_path(article: Dict[str, Any]) -> Path:
    slug = article.get("slug") or slugify(article.get("title", "article"))
    return SITE_DIR / "articles" / f"{slug}.html"


def safe_inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    def link_repl(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        if not re.match(r"^(https?://|/|\.{0,2}/)", url):
            return label
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, escaped)


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    output: List[str] = []
    list_buffer: List[str] = []

    def flush_list() -> None:
        if list_buffer:
            output.append("<ul>")
            output.extend(f"<li>{safe_inline_markdown(item)}</li>" for item in list_buffer)
            output.append("</ul>")
            list_buffer.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_list()
            continue
        if stripped.startswith("- "):
            list_buffer.append(stripped[2:])
            continue
        flush_list()
        if stripped.startswith("### "):
            output.append(f"<h3>{safe_inline_markdown(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            output.append(f"<h2>{safe_inline_markdown(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            output.append(f"<h1>{safe_inline_markdown(stripped[2:])}</h1>")
        elif stripped == "---":
            output.append("<hr>")
        else:
            output.append(f"<p>{safe_inline_markdown(stripped)}</p>")
    flush_list()
    return "\n".join(output)


def render_page(
    title: str,
    description: str,
    body_html: str,
    site_title: str,
    head_extra: str = "",
) -> str:
    rendered_head_extra = f"  {head_extra}\n" if head_extra else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} | {html.escape(site_title)}</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
  <link rel="stylesheet" href="/assets/style.css">
{rendered_head_extra.rstrip()}
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/">{html.escape(site_title)}</a>
    <nav>
      <a href="/articles/">記事一覧</a>
      <a href="/sitemap.xml">Sitemap</a>
    </nav>
  </header>
  <main class="layout">
    {body_html}
  </main>
  <footer class="site-footer">
    <p>広告を含む場合があります。AIの過大評価や誤認表現を避け、一次経験と限界を明記します。</p>
  </footer>
</body>
</html>
"""


def extract_urls(text: str) -> List[str]:
    return re.findall(r"https?://[^\s)\"']+", text)


def parse_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return None
    return None
