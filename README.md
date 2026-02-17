# ae2-dashboard
MinecraftのAE2(Applied Energistics 2)で、ネットワークの在庫管理をするダッシュボードです。ゲーム内のCraftOS(ComputerCraft及びCC: Tweaked)で動かすためのLuaコードと、Webブラウザから見るダッシュボードのコード(Python/JSTSフロントバック)です。

## Note for AI Tools

This repository contains large static asset directories.
Do NOT scan or enumerate icon or build artifacts.

Please read **AI_GUIDE.md** before any investigation or implementation.


## Architecture Overview

```
CC:Tweaked (Lua)              Cloud Run (Python)             Browser
┌────────────┐  HTTP POST   ┌──────────────────┐  GET /dashboard/ui
│ AE2 Network├─────────────►│ FastAPI (/ingest) ├──────────────────► Heatmap UI
│ in Minecraft│   /ingest    │                  │                    (Vite SPA)
└────────────┘              │  ┌──── GCS ─────┐ │
                            │  │ snapshots    │ │
                            │  └──────────────┘ │
                            │  ┌── PostgreSQL ─┐ │
                            │  │ inventory_*   │ │
                            │  └──────────────┘ │
                            └──────────────────┘
```

- **`cc/`** — Minecraft内のCC:Tweakedで動くLuaスクリプト。AE2ネットワークの在庫を定期的にHTTP POSTで送信する
- **`collector/`** — FastAPI バックエンド。データ受信（`/ingest`）、集計、ダッシュボードAPI、UIの配信を担当
  - `collector/app/ops_ui/ui-src/` — Vite でビルドされるフロントエンド（ヒートマップUI）
- **`scripts/`** — env読み込み・Docker起動・Cloud Runデプロイ用のシェルスクリプト
- **`migrations/`** — PostgreSQLスキーマ変更用SQL

## Prerequisites

| ツール | バージョン | 備考 |
|---|---|---|
| Python | 3.12+ | Dockerfile基準 |
| Node.js | 20+ | UIビルド用 (Dockerビルド時に自動で使用) |
| Docker | 20+ | `make dev` で使用 |
| gcloud CLI | — | `make deploy` で使用（ローカル開発のみなら不要） |

## Quick Start

```bash
# 1. リポジトリをクローン
git clone https://github.com/wakadorimk2/ae2-dashboard.git
cd ae2-dashboard

# 2. .env を作成（各変数は下記 Configuration を参照）
cp .env.example .env
# ⚠ .env には秘密情報が含まれます。絶対にコミットしないでください。

# 3-A. Docker でローカル起動（推奨：UIビルドも含む）
make dev
# → http://localhost:8080/dashboard/ui でダッシュボードが開く

# 3-B. Python だけで起動（UIビルドなし・API開発向け）
pip install -r collector/requirements.txt
make dev-local
# → http://localhost:8080/ でAPIが動く

# 4. テスト実行
pip install -r collector/requirements-dev.txt
make test
```

## Configuration

`.env` に設定する環境変数の一覧。

### アプリケーション

| 変数名 | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `APP_NAME` | — | `ae2-collector` | アプリ名（APIレスポンスに表示） |
| `PORT` | — | `8080` | リッスンポート |
| `LOG_RAW` | — | `0` | `1` で受信ペイロードを全ログ出力 |
| `MAX_ITEMS` | — | `200000` | 1回のingestで受け入れる最大アイテム数 |
| `DEFAULT_WORLD_ID` | — | `atm9` | world_id未指定時のデフォルト値 |
| `MIN_DT_SEC` | — | `10` | 増減率計算をスキップする最小時間差（秒） |

### GCP / Cloud Run

| 変数名 | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `GCP_PROJECT` | デプロイ時 | — | GCPプロジェクトID |
| `GOOGLE_CLOUD_PROJECT` | デプロイ時 | — | GCPプロジェクトID（Cloud Run用） |
| `GCS_BUCKET` | Yes | — | スナップショット保存先のGCSバケット名 |
| `GCS_PREFIX` | — | `raw` | GCSオブジェクトのプレフィックス |
| `REGION` | — | `us-west1` | Cloud Runリージョン |
| `SERVICE` | デプロイ時 | — | Cloud Runサービス名 |

### Database (PostgreSQL)

| 変数名 | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `DB_HOST` | Yes | — | PostgreSQLホスト |
| `DB_PORT` | Yes | — | ポート（通常 `5432`） |
| `DB_NAME` | Yes | — | データベース名 |
| `DB_USER` | Yes | — | 接続ユーザー |
| `DB_PASSWORD` | Yes | — | パスワード |
| `DB_SSLMODE` | — | `require` | SSL接続モード |

### テスト / その他

| 変数名 | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `SERVICE_URL` | テスト時 | — | 手動テスト用のCloud Run URL |
| `NETWORK_ID` | テスト時 | — | 手動テスト用のネットワークID |

## 使い方
```bash
make dev        # ← ローカルテスト
make deploy     # ← 本番
make dev-local  # ← Pythonだけ触るとき
make help       # ← 忘れたら見る
```

## 実装方針
LLMに調査や実装を依頼する際のスニペット。
- 調査:
```text
調査モード。AI_GUIDE.mdを前提にコードを一切変更せずに対応してください。...(以下指示を書く)
```
- 実装:
```text
実装モード。AI_GUIDE.mdを前提に最小差分で対応してください。...(以下指示を書く)
```

## メモ
### 2026-1-19 16:54
久しぶりに再開してる～。記憶はぼんやりだけど、またやってみようかなと。とりあえずUI弄りつつマイクラも改めてプレイしながら感触を確かめてる。
### 2026-1-8 16:27
DBを導入しつつある。BigQueryは運用重そうだし、今のGCS保存はレイテンシ上げたときにきつそうなので、Cloud SQLでひとまずPostgreSQLのテーブルを作った。
### 2026-1-7 7:16
GitHub Copilot Proに加入して、PRをレビューしてもらうようにした。めっちゃ的確なものが飛んできつつ、それに圧倒されない自分がいて自信がつく。知らないこともたくさんで勉強になるし。とりあえずDAG集計用のaggregate APIを生やした上、セキュリティとテストも追加したので、今後のAPI追加が楽になりそう。
### 2026-1-5 14:36
おはうお。バグ潰しとかTS移行や型を厳しくして、UIに手を加える下地ができた。今はDAGと株ヒートマップ風のUIを結びつける実装を進めている。あとレビューもmain直pushを禁止ルールを作って仕組み的にできないようにした。GitHub上でCodexにレビューしてもらってからmergeする感じで。
### 2026-1-5 9:24
どうも、お久しぶりです……夢中で開発していたら3日経っていた……クラウドへの以降が完了したあとは三日三晩開発を続けていた。どうなったかというと、UI/UXを整理したり、TS以降したり、Dockerのローカルテスト環境を導入したりと、わりと足回りの強化をやっていた。もちろんデータの方もDAGとトポロジカルソートという新しい概念に辿り着いたり、アイコン足したりグラフや株ヒートマップ風のUIを足したり。すごい密度だった。
### 2026-1-2 8:55
Cloud Runへのデプロイと、GCSにファイルを保存するまで完了した。
このあとはCC側のfingerprint強化とかやってる。
### 2026-1-2 6:00
データを取り出すにも全アイテムだと数千種類(書いてる時点で2500種類)あり、塩水とか塩素とか1.0M単位で作っているものもあるし、ツールとか電池とかはNBT爆発のリスクもあるので、軽くLua側で正規化してから、Cloud Runに送って、GCSに保管。そのあとでダッシュボード側は考えよう。現状の候補はGCPのCloud Monitoring。
### 2026-1-2 4:58
いろいろチャッピーと検討してたら、CC側で複雑な処理をするのは避けて、分析とかUIは外部のサービス(GCPなりAWSなりのPrometheus + Grafana系)に投げたほうが楽そうということで、まずはCCでデータだけを取り出すコードを書く
### 2026-1-2 3:50
マイクラのAll The MOD 9で遊んでたら、AE2のネットワークを管理したくなって、在庫管理とかクラフト状態みたいなのを常に監視できると嬉しいなぁと思った結果、ComputeCraftを発見してLuaを書こうと思った。でもゲーム内のエディターだと限界があるので、GitHubにコードを置いて、VSCodeでコード書いて、それをCraftOSからwgetできる(らしい)のでやってみる。

## APIメモ
* Endpoint: `POST /jobs/aggregate`
* Headers:

  * `X-API-Key: <key>`
  * `X-Timestamp: <unix seconds>`
  * `X-Nonce: <uuid>`
* Body:

  * `{"network_id": "<string>"}`
* Response:

  * `{"ok": true, "ts": <unix_timestamp>, "view_path": "gs://.../latest.json"}`

## テストメモ
### Aggregate (manual test)

```bash
# .env
SERVICE_URL=https://ae2-dashboard-xxxx.run.app
NETWORK_ID=base-main

# run (recommended)
source scripts/env.sh
python collector/scripts/aggregate_real.py
```

Required headers:

* `X-API-Key`
* `X-Timestamp`
* `X-Nonce`