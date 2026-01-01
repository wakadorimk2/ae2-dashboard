# ae2-dashboard
MinecraftのAE2(Applied Energistics 2)で、ネットワークの在庫管理をするダッシュボードをゲーム内のCraftOS(ComputerCraft及びCC: Tweaked)で動かすためのLuaコードです。

## メモ
### 2025-1-2 4:58
いろいろチャッピーと検討してたら、CC側で複雑な処理をするのは避けて、分析とかUIは外部のサービス(GCPなりAWSなりのPrometheus + Grafana系)に投げたほうが楽そうということで、まずはCCでデータだけを取り出すコードを書く
### 2025-1-2 3:50
マイクラのAll The MOD 9で遊んでたら、AE2のネットワークを管理したくなって、在庫管理とかクラフト状態みたいなのを常に監視できると嬉しいなぁと思った結果、ComputeCraftを発見してLuaを書こうと思った。でもゲーム内のエディターだと限界があるので、GitHubにコードを置いて、VSCodeでコード書いて、それをCraftOSからwgetできる(らしい)のでやってみる。