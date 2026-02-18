# ae2-dashboard/collector
マイクラ側で集めたデータをCloud Runで受け取って貯めるプログラムです。

## UI snapshot fixture (snapshot=1)
ローカルで `?snapshot=1` を使う場合は、スナップショットJSONを
`collector/app/ops_ui/static/ui/dist/fixtures/snapshot.json` に配置してください。
（巨大JSONはこのリポジトリで移動せず、作業者が手動でコピーする運用）

## Test (curl)
Legacy schema:
```bash
curl -i -X POST -H "Content-Type: application/json" \
  -d '{"items":[{"raw_name":"minecraft:stone","amount":1}]}' \
  http://localhost:8000/ingest
```

New schema (entries):
```bash
curl -i -X POST -H "Content-Type: application/json" \
  -d '{"entries":[{"kind":"item","raw_name":"minecraft:stone","amount":1}]}' \
  http://localhost:8000/ingest
```
