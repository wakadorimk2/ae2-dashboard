# ae2-dashboard
MinecraftのAE2(Applied Energistics 2)で、ネットワークの在庫管理をするダッシュボードです。ゲーム内のCraftOS(ComputerCraft及びCC: Tweaked)で動かすためのLuaコードと、Webブラウザから見るダッシュボードのコード(Python/JSTSフロントバック)です。

## Note for AI Tools

This repository contains large static asset directories.
Do NOT scan or enumerate icon or build artifacts.

Please read **AI_GUIDE.md** before any investigation or implementation.


## 使い方
```bash
make dev        # ← ローカルテスト
make deploy     # ← 本番
make dev-local  # ← Pythonだけ触るとき
make help       # ← 忘れたら見る
```

## メモ
### 2025-1-5 9:24
どうも、お久しぶりです……夢中で開発していたら3日経っていた……クラウドへの以降が完了したあとは三日三晩開発を続けていた。どうなったかというと、UI/UXを整理したり、TS以降したり、Dockerのローカルテスト環境を導入したりと、わりと足回りの強化をやっていた。もちろんデータの方もDAGとトポロジカルソートという新しい概念に辿り着いたり、アイコン足したりグラフや株ヒートマップ風のUIを足したり。すごい密度だった。
### 2025-1-2 8:55
Cloud Runへのデプロイと、GCSにファイルを保存するまで完了した。
このあとはCC側のfingerprint強化とかやってる。
### 2025-1-2 6:00
データを取り出すにも全アイテムだと数千種類(書いてる時点で2500種類)あり、塩水とか塩素とか1.0M単位で作っているものもあるし、ツールとか電池とかはNBT爆発のリスクもあるので、軽くLua側で正規化してから、Cloud Runに送って、GCSに保管。そのあとでダッシュボード側は考えよう。現状の候補はGCPのCloud Monitoring。
### 2025-1-2 4:58
いろいろチャッピーと検討してたら、CC側で複雑な処理をするのは避けて、分析とかUIは外部のサービス(GCPなりAWSなりのPrometheus + Grafana系)に投げたほうが楽そうということで、まずはCCでデータだけを取り出すコードを書く
### 2025-1-2 3:50
マイクラのAll The MOD 9で遊んでたら、AE2のネットワークを管理したくなって、在庫管理とかクラフト状態みたいなのを常に監視できると嬉しいなぁと思った結果、ComputeCraftを発見してLuaを書こうと思った。でもゲーム内のエディターだと限界があるので、GitHubにコードを置いて、VSCodeでコード書いて、それをCraftOSからwgetできる(らしい)のでやってみる。