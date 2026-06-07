# AI業務効率化アフィリ自動収益サイト

GitHub PagesとGitHub Actionsで、AI業務効率化に特化したSEO記事を生成、品質チェック、静的サイト化、週次レポート作成まで自動化するためのリポジトリです。

## 重要な前提

- 月100万円は保証しません。平均成果報酬5,000円なら月200件成約が必要です。
- 初期KPIは90日で「公開100ページ、月間検索流入1,000、アフィリクリック50、初成果1件以上」です。
- 未承認アフィリリンクは公開されません。`data/affiliate_catalog.yml` で `approved: true` にした案件だけが記事に挿入されます。
- DM自動送信、X大量自動投稿、虚偽レビュー、AI万能化表現は実装対象外です。

## ローカル実行

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt

python3 scripts/generate_articles.py --count 3
python3 scripts/build_site.py
python3 scripts/weekly_report.py
python3 scripts/launch_audit.py
python3 scripts/quality_check.py --include-site
python3 -m pytest
```

生成物:

- `content/`: 生成済みMarkdown記事
- `site/`: GitHub Pages公開用HTML
- `reports/`: 週次レビュー

## 収益リンクの入れ方

1. A8.net、楽天アフィリエイト、Amazonアソシエイトなどで提携を確認する。
2. `data/affiliate_catalog.yml` の該当案件に `affiliate_url`、`payout_yen`、`last_checked` を入れる。
3. 案件条件とPR表記を確認してから `approved: true` にする。
4. `python3 scripts/quality_check.py` を通す。

`approved: true` なのに `affiliate_url` が空、`example.com`、PR表記なし、確認日なしの場合はCIで落ちます。承認済みリンクは記事から直接外部URLへ出さず、`/go/{item_id}.html` のリダイレクトページを経由します。

## 100記事までの自動生成

`data/topics.yml` の固定テーマに加えて、`data/topic_templates.yml` の「業種 × 業務 × AIツール」から長尾SEOテーマを自動展開します。現設定では100件以上の候補があり、GitHub Actionsの `daily_generate.yml` が毎日2本ずつ未生成テーマを記事化します。

## クリック計測

GitHub Pages単体ではサーバー側クリックログを取得できません。そのため、承認済みアフィリリンクは `/go/` ページを経由し、`data/tracking.yml` でPlausibleまたはGoogle Analyticsを設定した場合に `affiliate_click` イベントを送ります。

設定例:

```yaml
analytics:
  provider: google_analytics
  google_analytics_measurement_id: G-XXXXXXXXXX
```

## GitHub Actions

- `.github/workflows/daily_generate.yml`: 毎日2記事生成、品質チェック、サイトビルド、変更があればコミット
- `.github/workflows/deploy.yml`: `site/` をGitHub Pagesへ公開
- `.github/workflows/weekly_review.yml`: 毎週日曜にレポート生成

GitHub Pagesを使う場合は、リポジトリ Settings の Pages で GitHub Actions 公開を有効にしてください。

## ローンチ監査

```bash
python3 scripts/launch_audit.py
```

公開・収益化に必要な状態を監査し、`reports/launch-audit-YYYY-MM-DD.md` に出力します。未達がある場合は終了コード2を返します。現時点では、GitHub remote、承認済みアフィリリンク、分析タグが外部作業待ちとして出ます。

## GitHub Secrets

現時点のパイプラインは外部APIなしで動きます。将来API連携を足す場合は、APIキーやアフィリIDをGitHub Secretsへ入れ、コードやログに出さないでください。

推奨Secrets名:

- `A8_TRACKING_ID`
- `RAKUTEN_AFFILIATE_ID`
- `AMAZON_ASSOCIATE_TAG`

## 運用ルール

- 週1回、`reports/weekly-YYYY-MM-DD.md` を確認する。
- 90日で初成果がなければ、記事量産ではなくテーマ、案件単価、検索意図を見直す。
- 本筋のAI導入支援Phase 1を圧迫しないよう、手動作業は週30分以内に制限する。
