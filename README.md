# ForSSCommanders

現在の情報群ごとの周期・専用設定・非dueの扱いは[収集頻度表](WowsExtractor-torpedoes-client-test/docs/COLLECTION_CADENCE.ja.md)を参照。

最新実機状況：[B46・0.3.38](WowsExtractor-torpedoes-client-test/docs/VALIDATION_B46_0.3.38.ja.md)は限定条件（heavy OFF・独立4群ON）で minFPS 約50以上・カクつきなし（ユーザー報告、録画なし）。1,335 records（active 1,333）、HP平均約2 Hz、比較／damage平均約1 Hz・非due省略、独立 profiler phase を確認。depth／WaveHit／gun は全1,333 available、Battery 272 available／1,061 notSampled。遠距離2 Hz・多数魚雷・因果的 FPS 改善率は未検証。試験後 collector 退避済み。以下の未実機表記は各版公開時の履歴。

最新ソース：**0.3.40-radius-l5**（557 passed, 9 skipped＋9 module checker成功・未導入／未実機。skipはWoWS起動中のためinstaller 9件が安全上skip、私有replayは実施）。魚雷の分類半径をL/3から`R=L/5`へ正式変更し、L/5～L/3帯はLOWになる。自艦と厳密boolで確認できた魚雷は全距離HIGHのまま。境界上HIGH・近5Hz／遠平均2Hz・5秒再分類は維持し、1Hz遠方化ではない。0.3.38実機記録（L/3時点）の評価と、今回の未実機変更を区別する。

## 最近の版別到達点（履歴）

- 0.3.37 `independent-submarine`：自艦深度／Battery／WaveHit を診断から独立取得（既定OFF・collection必須）。
- 0.3.36 `damage-cadence`：damage イベント受付を維持し、snapshot 生成・出力を1 Hz化。
- 0.3.35 `health-cadence`：共通HP群を平均2 Hz、avatar 照合／集計を1 Hz へ分離。
- 0.3.34 `initial-torpedo-parameters`：魚雷性能・弾薬 params を戦闘初回のみ meta へ移動。
- 0.3.33 `torpedo-sampling-groups`：魚雷を5秒ごとに距離分類、近距離5 Hz／遠距離平均2 Hz。
- 0.3.32：砲弾道計算・専用イベント・`ballistics` 出力を全撤去。
- 0.3.31 `calibration-spatial-index`：較正の距離比較候補を空間 index で絞り込み。

詳細・制約・未確認事項は [TASKS.md](TASKS.md)、[FPS専用タスク](WowsExtractor-torpedoes-client-test/docs/FPS_TASKS.ja.md)、[既知の問題](WowsExtractor-torpedoes-client-test/docs/KNOWN_ISSUES.ja.md) を参照。

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

0.3.14導入後「自艦が沈むまでminFPS 25、撃沈後は110まで回復」と報告されています（外部記録ツール未使用）。因果は未確定です。B46（0.3.38・heavy OFF・独立4群ON）ではユーザー報告 minFPS 約50以上・カクつきなしを確認しましたが、今回は魚雷同時最大6本・low群0であり、遠距離2 Hz や多数魚雷時の FPS は未検証です。因果的な改善率・開始直後 FPS 低下も未解明です。

現行ソースは **`0.3.40-radius-l5`**（offline検証済み・未導入／未実機）。魚雷は5秒再分類で、自艦の厳密bool Trueは全距離HIGH、他は`L=min(map width,height)`のL/5内・境界上HIGH／外LOW平均2Hzです。collection/diagnostics/profiler/独立群はすべて既定OFFです。state は core tick 0.2 秒（約5 Hz、0.1 秒明示で10 Hz互換）を基準とし、各情報群の期限・sample metadata に応じて取得を省略・出力します（同一 `state.json` ファイルに出力されるだけで、すべての項目が毎tick揃うわけではありません）。HP 2 Hz・avatar 比較1 Hz・damage 1 Hz・自艦 depth／Battery／WaveHit／gun reload の独立取得は、明示ON・collection必須で利用可能です。意味・単位・実機 FPS 効果には制約が残ります。通常プレイでは引き続き mod 退避を推奨します。

旧0.3.1ではSteam版build 13357625の訓練戦で、魚雷位置・type、
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
ATMを残したままcollectorだけを入れる場合は、明示的に `install-13357625.bat --with-atm`（PowerShellでは `-WithAtm`）を使います。ATMは同梱・自動ダウンロードされません。ATMを退避した場合は、導入後に `restore-atm-13357625.bat` で戻します。復元先conflict時は上書きせず停止します。
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
