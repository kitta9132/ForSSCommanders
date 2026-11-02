# ForSSCommanders

- [開発タスク・残課題](TASKS.md)（仮マップはパラメーター確認用。本番マップはmod完成後に別途開発）
- [開発方針](DEVELOPMENT.md)
- [AI向け指示・Git運用](.ai/INSTRUCTIONS.md)

World of Warshipsの潜水艦向け外部2Dマップと、公開ModsAPIを使う戦闘情報収集modの開発プロジェクトです。

目標・収集層の責務は [DEVELOPMENT.md](DEVELOPMENT.md)、AIの共同作業・自律進行・Git運用は [.ai/INSTRUCTIONS.md](.ai/INSTRUCTIONS.md) を参照してください。

現在のソース・日本語資料は [`WowsExtractor-torpedoes-client-test/`](WowsExtractor-torpedoes-client-test/) にあります。

- [導入・概要](WowsExtractor-torpedoes-client-test/README.ja.md)
- [潜水艦probe短時間試験](WowsExtractor-torpedoes-client-test/docs/TEST_SUBMARINE_PROBE.ja.md)
- [元仕様との詳細対応表](WowsExtractor-torpedoes-client-test/docs/SPEC_COVERAGE_0.3.1.ja.md)
- [簡易2Dマップ](WowsExtractor-torpedoes-client-test/docs/SIMPLE_MAP.ja.md)

## 現在の状態

### 最優先：通常プレイ時のFPS報告

0.3.14導入後「自艦が沈むまでminFPS 25、撃沈後は110まで回復」と報告されています（外部記録ツール未使用）。mod内部のtick・state書込は別に戦闘中継続するため、因果は未確定です。通常プレイでは収集modのロード対象外への退避を推奨します。0.3.15-performance-safetyは**既定収集停止**の安全版で、FPS改善済み・性能改善確認済みではありません。ゲーム稼働中の変更や追加FPS比較試験は行いません。[事故記録](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_INCIDENT_0.3.14.ja.md)

現行の安全版ソースは `0.3.15-performance-safety`（未導入）。既定ではbattle収集を停止し、同期収集経路を開始しません。収集を明示有効化しても重い診断は別opt-inです。これはFPS改善確認ではありません。旧開発ソース0.3.14までの内容はID対応候補・魚雷の明示深度候補を含み、詳細と残課題は [TASKS.md](TASKS.md) を参照してください。旧0.3.1ではSteam版build 13357625の訓練戦で、魚雷位置・type、
ATM由来の誘導/被発見状態、移動履歴による座標較正などを試験しています。
簡易2Dマップのグリッドとゲーム内位置が概ね一致することをテスターが目視確認しました。
12対12・別地図・失探時の鮮度などは未検証です。完成版ではありません。

ATM本体や第三者の画像、個人情報を含む戦闘ログ・記録は同梱しません。
ATM由来のUI状態はATMの別途導入が必要で、取得できない場合はunknownとして扱います。

## Gitから利用する場合

### この作業環境の運用

正本は `WowsExtractor-torpedoes-client-test/`。旧日付付きフォルダーは削除・Git除外済みです。通常の開発ではZIPを作成しません。AIによる導入・コミットの担当は [.ai/INSTRUCTIONS.md](.ai/INSTRUCTIONS.md) を参照。以下のZIP生成は配布が必要な場合のみです。

チェックサム・一覧・一括ソースは生成物のためGitへ含めません。
インストーラーはチェックサムを必要とするため、まずPython 3.10以上で配布物を生成してください。
既存の出力ZIPは上書きされません。必要なら新しい出力名を指定します。

```powershell
cd WowsExtractor-torpedoes-client-test
python tools/build_bundle.py --output ../ForSSCommanders-bundle.zip
```

その後、同フォルダーの `install-13357625.bat` で導入します。ゲームを先に終了してください。
ATMありで試験する場合、導入後に `restore-atm-13357625.bat` を実行してください。
既存modのバックアップと、実際に起動するbuildの確認を推奨します。

## テスト

```powershell
cd WowsExtractor-torpedoes-client-test
python -m pytest -q
```

pytestが必要です。Node.jsがない場合は任意のJSロジックテスト1件をスキップします。
ゲームmodはPython 2.7想定、外部ツールはPython 3.10以上です。

## ライセンス・出自

MIT。[原著作権表示とライセンス](WowsExtractor-torpedoes-client-test/LICENSE)。
収集modは [Tz-WIND/8111_for_wows](https://github.com/Tz-WIND/8111_for_wows) 由来です。
公式リリースやWargamingによる動作保証ではありません。
