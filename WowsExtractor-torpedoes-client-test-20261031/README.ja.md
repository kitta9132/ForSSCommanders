# WowsExtractor 魚雷出力版：実機テスト用パッケージ

作成日：2026-10-31（日本時間）  
modバージョン：`0.3.1-map-motion` / ModsAPI：`API_v1.0`

元仕様と実機取得状況の最新版：[詳細対応表](docs/SPEC_COVERAGE_0.3.1.ja.md)。

**簡易2Dマップ**：`launch-map-13357625.bat` をダブルクリック。
ゲーム側modの変更・再起動は不要です。[使い方と制約](docs/SIMPLE_MAP.ja.md)。

0.3.1はゲーム環境にAttributeError名がない場合の診断処理停止を修正しました。

0.3.0は移動履歴による地図較正と魚雷の推定運動情報を追加。
詳細と試験手順は [docs/MAP_MOTION.ja.md](docs/MAP_MOTION.ja.md)。0.3.1で実機確認済みです。

0.2.3はATMのisSpotted抽出を追加し、0.3.1でtrue値の取得を実機確認しました。
各項目の取得状況は [docs/ACQUISITION_STATUS.ja.md](docs/ACQUISITION_STATUS.ja.md) を参照。

0.2.2は読み取り専用のUI魚雷プローブを追加した診断版です。
UI/APIのID対応、ATM誘導状態とその変化を試験範囲で実機確認済みです。

0.2.1では、戦闘画面の表示が戦闘開始より先に通知されるbuildに対応しました。
両イベントがそろってから収集を開始し、メタ情報の書き込み失敗を成功と表示しません。
反映にはゲーム終了・インストーラー再実行・ゲーム再起動が必要です。

WoWSの公開ModsAPIで取れた魚雷情報を、ゲーム内modが `state.json` に書き出します。最優先の確認項目は **`torpedoes[].type` の生値と変化**です。

**build 13357625の訓練戦で実機確認を進めています。** ATM状態はdataHubから直接読み取り、
isHoming/isSpottedを取得します。UI→Flash→Pythonの橋渡しは使用していません。
12対12・別地図・失探時の鮮度や外部表示の位置一致は未検証です。

## まずやること

1. ゲームを終了し、既存の `res_mods/PnFMods/WowsExtractor` と `PnFModsLoader.py` をバックアップします。ATMあり環境で `install-13357625.bat` を使う場合、ATM本体とATM専用unboundは自動で退避されます。手動で入れる場合は同じファイルをロード対象外へ移動します（詳細は [バージョン固定インストーラー](docs/INSTALL_BAT.ja.md)）。
2. このパッケージの `res_mods/PnFMods/WowsExtractor` を、実際に起動しているbuildの `res_mods/PnFMods/` にコピーします。
3. `res_mods/PnFModsLoader.py` がなければ、同梱の同名ファイルをコピーします。**既存のものは上書きしません。** 同梱ファイルが0バイトなのは仕様です。
4. ゲームを起動し、訓練戦で魚雷を発射します。
5. 導入先の `WowsExtractor/state.json` が更新され、`torpedoStatus` と `torpedoes` があることを確認します。

```text
World_of_Warships/
└─ bin/
   └─ <実際に起動するbuild番号>/
      └─ res_mods/
         ├─ PnFModsLoader.py
         └─ PnFMods/
            └─ WowsExtractor/
               ├─ Main.py
               ├─ battle_identity.py
               ├─ damage_tracker.py
               ├─ emit_guard.py
               ├─ ui_health.py
                ├─ torpedo_telemetry.py
                ├─ map_calibration.py
               └─ config.example.ini
```

`config.example.ini` は必要なら `config.ini` にコピーします。未作成なら標準設定で動きます。`Main.py` 単体では動きません。

## この版でできること

- 可視魚雷の公開7属性、発射元の公開属性、味方／敵の整理情報を出力。
- 自艦の発射管状態、選択魚雷弾ID、APIが返す場合の公開弾パラメーターを出力。
- APIの非対応・取得失敗・正常取得で0本を区別。
- 元プロジェクトの艦船・自艦・名簿・地図・ダメージ・砲弾情報の収集を維持。
- 任意の外部記録ツールで、更新されるJSONをJSONLの履歴として保存。

外部簡易2Dマップと読み取り専用localhost HTTPサーバーを任意ツールとして含みます。
WebSocketやゲーム操作の自動化は含みません。mod本体にゲーム外Pythonやpipパッケージは不要です。
外部ツールはPython 3.10以上を使用し、追加pipパッケージは不要です。

## ドキュメント一覧

| 文書 | 内容 |
| --- | --- |
| [導入・削除・設定](docs/INSTALL.ja.md) | コピー先、ローダー、設定、元に戻す手順 |
| [バージョン固定インストーラー](docs/INSTALL_BAT.ja.md) | build 13357625用。ATM自動退避と復元を含む |
| [出力仕様](docs/OUTPUT_SPEC.ja.md) | 全トップレベル項目、魚雷関係全フィールド、欠損値、単位、例 |
| [元仕様との詳細対応表](docs/SPEC_COVERAGE_0.3.1.ja.md) | 取得済み・条件付き・推定・未取得を項目別に整理 |
| [外部簡易2Dマップ](docs/SIMPLE_MAP.ja.md) | localhost起動、マーカー、更新停止・終了時の表示 |
| [実機テスト手順](docs/TEST_PLAN.ja.md) | `type`最優先、ATMなし／あり、1ping／2ping、終了・再入場 |
| [履歴記録ツール](docs/RECORDER.ja.md) | Python 3用の任意ツール、コマンド、JSONL形式 |
| [問題の切り分け](docs/TROUBLESHOOTING.ja.md) | ファイルが出ない／魚雷0本／type不変など |
| [設計と未確認事項](docs/DESIGN.ja.md) | typeとisHomingの違い、v1/v2、将来のUI経路 |
| [テスト結果・再現方法](docs/VALIDATION.ja.md) | オフライン確認と実機確認の境界 |
| [実機テスト記録用紙](docs/TEST_REPORT_TEMPLATE.ja.md) | コピーして記入する報告テンプレート |
| [全ファイル一覧](FILES.md) | 全ソース・サンプル・資料へのリンク |
| [全ソース一括表示](ALL_SOURCE.txt) | 実行用・テスト用ソースの全文。導入には使わず閲覧用 |

## 読み間違えやすい点

- `Torpedo.type` とUI側typeは試験範囲で一致しました。両方を別項目として出力し、全状況での同一性は保証しません。
- ATMでは誘導レベル1→`acoustic`、2→`magnetic`。**`type`だけで現在も誘導中とは断定しません。**
- `normal` を一律に「誘導不能」、`magnetic` を別の物理的な磁気魚雷、と解釈しません。まずマーカーの生値として保存します。
- `isHoming/isSpotted` はATM等の供給に依存し、取得不可はnullです。nullや項目欠落はfalseではありません。
- ファイルは毎回上書きされます。**戦闘終了後の `state.json` だけでは戦闘中の変化は残りません。** 履歴記録を推奨します。

## 出自・ライセンス

ベース：[Tz-WIND/8111_for_wows](https://github.com/Tz-WIND/8111_for_wows)、コミット `28470b6ff0c05bac8aa41bd7d986daa6814242e2`。元プロジェクトのクライアント側に魚雷出力を追加しています。
このパッケージは独立した公式リリースではありません。ATM本体・署名済みAPI v2ファイル・第三者の画像等は再配布していません。
MITライセンス。原著作権表示を含む [LICENSE](LICENSE) を同梱しています。

`SHA256SUMS.txt` は収録ファイルのチェックサムです。配布者本人を証明する電子署名ではありません。
