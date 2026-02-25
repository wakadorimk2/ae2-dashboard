## Checklist
- [ ] Draftのまま Copilotレビューを待つ（または確認済み）
- [ ] Copilotの指摘に対応 / 理由を書いた
- [ ] テスト実行（最低 `make test`）
- [ ] Draft解除してから Merge
- [ ] 危険ゾーン確認（`migrations/` / deploy / secrets に触れた場合は下記に理由を記載）
- [ ] ロールバック手順の確認（DBマイグレーション・デプロイを含む場合は手順を記載）
