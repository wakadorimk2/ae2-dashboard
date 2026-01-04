# ae2-dashboard/collector
マイクラ側で集めたデータをCloud Runで受け取って貯めるプログラムです。

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
