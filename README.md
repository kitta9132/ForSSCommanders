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

0.3.14導入後「自艦が沈むまでminFPS 25、撃沈後は110まで回復」と報告されています（外部記録ツール未使用）。因果は未確定です。通常プレイでは収集modのロード対象外への退避を推奨します。現行0.3.29-torpedo-state-samplingは**source only・未導入**で、collection/diagnostics/profiler/position fallbackとdepth/state samplerは既定OFFです。B37ではavatar map/healthを取得できましたが、strict `avatar.playerId`は全738 stateでunmatchableでした。0.3.27の`avatar.id`は未確定candidateとして別出力し、確定join・既存coverageは変更しません。0.3.28の専用depth samplerはB40で262行のraw `0.14`を実機取得しましたが、単位・意味は未確認でunit=nullです。0.3.29は`isHoming`/`isSpotted`の固定2候補だけを最小1秒で独立sampleするopt-inを追加します。Python側のavailability/producerは未確認・unknownのままで、全collectionとAPI/UI IDの厳密一意性を確認できた場合のみ同frameへ付与します。FPS・新featureの実機値・実時間・API内部時間は未確認です。[B40深度記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_B40_0.3.28_TORPEDO_DEPTH.ja.md)／[事故記録](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_INCIDENT_0.3.14.ja.md)

現行ソースは `0.3.29-torpedo-state-sampling`（未導入）。collection/diagnostics/profiler/位置fallback/depth/state samplerは既定OFFです。state既定は0.2秒（約5Hz、0.1明示で10Hz互換）、全snapshot一体・群別周期なしです。depth/state samplerは別々の専用opt-inでdiagnosticsに依存せず、各最小1秒・最大64 entities。同時due時はheavy diagnosticsを含む3 probeで同sample torpedo collection getter／列挙を共有します。state samplerは固定`isHoming`/`isSpotted`のみ読み、GUI/API IDが完全・scalar・同型・全件一意の場合だけ付与します。sourceのproducerと意味はunknown/unverifiedで、誘導先ID・停止理由を表しません。B40ではdepth候補raw `0.14`を262行取得しましたが、単位・意味は未確認（unit=null）。非due/欠測に過去値は使わず、新featureの実機取得・FPS・実時間・API内部時間は未確認です。[出力仕様](WowsExtractor-torpedoes-client-test/docs/OUTPUT_SPEC.ja.md)と[TASKS.md](TASKS.md)を参照してください。旧0.3.1ではSteam版build 13357625の訓練戦で、魚雷位置・type、
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
