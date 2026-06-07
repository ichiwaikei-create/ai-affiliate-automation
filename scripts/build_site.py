from __future__ import annotations

import html
import json
from pathlib import Path

from automation_lib import (
    DATA_DIR,
    SITE_DIR,
    affiliate_go_url,
    approved_affiliate_items,
    article_output_path,
    load_articles,
    load_yaml,
    markdown_to_html,
    render_page,
    write_text,
)


STYLE = """
:root {
  color-scheme: light;
  --bg: #f7f8fb;
  --panel: #ffffff;
  --text: #1f2937;
  --muted: #667085;
  --line: #d9dee7;
  --accent: #0f766e;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
  line-height: 1.75;
  color: var(--text);
  background: var(--bg);
}
a { color: var(--accent); text-decoration-thickness: .08em; text-underline-offset: .18em; }
.site-header, .site-footer {
  max-width: 1040px;
  margin: 0 auto;
  padding: 20px;
}
.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--line);
}
.brand { font-weight: 700; color: var(--text); text-decoration: none; }
nav { display: flex; gap: 14px; font-size: 14px; }
.layout {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 20px 56px;
}
.hero {
  padding: 28px 0 20px;
  border-bottom: 1px solid var(--line);
}
.card-list {
  display: grid;
  gap: 16px;
  margin-top: 24px;
}
.article-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
}
.article-card h2 { margin: 0 0 8px; font-size: 20px; }
.meta, .disclosure { color: var(--muted); font-size: 14px; }
article {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 26px;
}
h1, h2, h3 { line-height: 1.35; }
h1 { font-size: 30px; }
h2 { margin-top: 34px; font-size: 23px; }
h3 { margin-top: 24px; font-size: 18px; }
ul { padding-left: 1.3rem; }
.site-footer { color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); }
@media (max-width: 640px) {
  .site-header { align-items: flex-start; flex-direction: column; }
  article { padding: 18px; }
  h1 { font-size: 25px; }
}
"""


def analytics_head(tracking):
    analytics = tracking.get("analytics", {})
    provider = analytics.get("provider", "none")
    plausible_domain = analytics.get("plausible_domain", "")
    ga_id = analytics.get("google_analytics_measurement_id", "")
    if provider == "plausible" and plausible_domain:
        domain = html.escape(plausible_domain, quote=True)
        return f'<script defer data-domain="{domain}" src="https://plausible.io/js/script.js"></script>'
    if provider == "google_analytics" and ga_id.startswith("G-"):
        measurement = html.escape(ga_id, quote=True)
        return f"""<script async src="https://www.googletagmanager.com/gtag/js?id={measurement}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', '{measurement}');
</script>"""
    return ""


def published_articles():
    articles = [a for a in load_articles() if a.get("status") == "published"]
    articles.sort(key=lambda a: (a.get("generated_at") or "", a.get("title") or ""), reverse=True)
    return articles


def build_index(articles, site, head_extra):
    cards = []
    for article in articles:
        path = f"/articles/{article['slug']}.html"
        cards.append(
            f"""<section class="article-card">
  <h2><a href="{html.escape(path)}">{html.escape(article['title'])}</a></h2>
  <p class="meta">{html.escape(article.get('keyword', ''))} / {html.escape(str(article.get('generated_at', '')))}</p>
  <p>{html.escape(article.get('description', ''))}</p>
</section>"""
        )
    if not cards:
        cards.append("<p>公開記事はまだありません。</p>")
    body = f"""<section class="hero">
  <h1>{html.escape(site['title'])}</h1>
  <p>{html.escape(site['description'])}</p>
  <p class="disclosure">広告を含む場合があります。未承認リンクや条件未確認の案件は掲載しません。</p>
</section>
<section class="card-list">
{''.join(cards)}
</section>"""
    return render_page(site["title"], site["description"], body, site["title"], head_extra=head_extra)


def build_articles_index(articles, site, head_extra):
    links = "\n".join(
        f"<li><a href=\"/articles/{html.escape(article['slug'])}.html\">{html.escape(article['title'])}</a></li>"
        for article in articles
    )
    body = f"<article><h1>記事一覧</h1><ul>{links}</ul></article>"
    return render_page("記事一覧", "公開済み記事の一覧", body, site["title"], head_extra=head_extra)


def build_article_page(article, site, head_extra):
    body = markdown_to_html(article["_body"])
    disclosure = html.escape(article.get("monetization_disclosure", ""))
    article_html = f"""<article>
  <p class="meta">{html.escape(article.get('keyword', ''))} / 更新日 {html.escape(str(article.get('updated_at', '')))}</p>
  <p class="disclosure">{disclosure}</p>
  {body}
</article>"""
    return render_page(article["title"], article.get("description", ""), article_html, site["title"], head_extra=head_extra)


def build_redirect_page(item, site, tracking):
    analytics = tracking.get("analytics", {})
    redirect = tracking.get("redirect", {})
    event_name = analytics.get("event_name", "affiliate_click")
    delay_ms = int(redirect.get("delay_ms", 450))
    fallback_text = redirect.get("fallback_text", "広告リンクへ移動しない場合はこちら")
    target_url = item["affiliate_url"]
    safe_target = html.escape(target_url, quote=True)
    target_js = json.dumps(target_url, ensure_ascii=False)
    safe_name = html.escape(item["name"])
    safe_provider = html.escape(item["provider"])
    payload = {
        "affiliate_id": item["id"],
        "provider": item["provider"],
        "category": item["category"],
    }
    payload_js = json.dumps(payload, ensure_ascii=False)
    event_name_js = json.dumps(event_name, ensure_ascii=False)
    body = f"""<article>
  <h1>{safe_name}</h1>
  <p class="meta">広告リンク / {safe_provider}</p>
  <p>{safe_name} の広告リンクへ移動します。提携条件とPR表記を確認済みのリンクだけを掲載します。</p>
  <p><a id="outbound-link" href="{safe_target}" rel="nofollow sponsored">{html.escape(fallback_text)}</a></p>
  <script>
  (function() {{
    var target = {target_js};
    var payload = {payload_js};
    try {{
      if (window.plausible) {{
        window.plausible({event_name_js}, {{ props: payload }});
      }}
      if (window.gtag) {{
        window.gtag("event", {event_name_js}, payload);
      }}
    }} catch (error) {{
      console.warn("affiliate event failed", error);
    }}
    window.setTimeout(function() {{
      window.location.href = target;
    }}, {delay_ms});
  }})();
  </script>
</article>"""
    noindex = '<meta name="robots" content="noindex,nofollow">'
    return render_page(f"{item['name']}へ移動", "広告リンクへのリダイレクトページ", body, site["title"], head_extra=noindex + "\n  " + analytics_head(tracking))


def build_sitemap(articles, site):
    base_url = site.get("base_url", "https://example.com").rstrip("/")
    urls = ["/"] + [f"/articles/{article['slug']}.html" for article in articles] + ["/articles/"]
    entries = "\n".join(f"  <url><loc>{html.escape(base_url + url)}</loc></url>" for url in urls)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
"""


def main() -> int:
    topics = load_yaml(DATA_DIR / "topics.yml")
    tracking = load_yaml(DATA_DIR / "tracking.yml")
    catalog = load_yaml(DATA_DIR / "affiliate_catalog.yml")
    site = topics["site"]
    articles = published_articles()
    head_extra = analytics_head(tracking)

    write_text(SITE_DIR / "assets" / "style.css", STYLE.strip() + "\n")
    write_text(SITE_DIR / ".nojekyll", "")
    write_text(SITE_DIR / "index.html", build_index(articles, site, head_extra))
    write_text(SITE_DIR / "articles" / "index.html", build_articles_index(articles, site, head_extra))
    for article in articles:
        write_text(article_output_path(article), build_article_page(article, site, head_extra))
    for item in approved_affiliate_items(catalog):
        write_text(SITE_DIR / affiliate_go_url(item).lstrip("/"), build_redirect_page(item, site, tracking))
    write_text(SITE_DIR / "sitemap.xml", build_sitemap(articles, site))
    write_text(SITE_DIR / "robots.txt", "User-agent: *\nAllow: /\nDisallow: /go/\nSitemap: /sitemap.xml\n")
    print(f"built {len(articles)} article pages into {SITE_DIR.relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
