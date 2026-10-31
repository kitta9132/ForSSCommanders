# 架空のサンプル

**このフォルダーの値はすべて説明用に生成した架空値です。WoWS実機の出力ではありません。**

| ファイル | 内容 |
| --- | --- |
| `state.live.json` | 通常フレームの形。魚雷1本、type=normalの架空例 |
| `state.ended.json` | 終了フレームの軽量形 |
| `meta.example.json` | modバージョン等を持つメタ情報の形 |
| `synthetic.type-changes.jsonl` | normal→acoustic→magneticを人工的に並べた記録ツール形式の例 |

`synthetic.type-changes.jsonl`は、実ゲームでこの順に変化することや、公開APIがこの値を返すことの証拠ではありません。閲覧や読み手の実装例として使います。

サンプルファイルをゲームのmodフォルダーへコピーしないでください。元のJSONを置き換える必要はありません。テスト記録と混ぜずに保管してください。
