# WowsExtractor 魚雷出力版：実機テスト用パッケージ

現在の情報群ごとの周期は[収集頻度表](docs/COLLECTION_CADENCE.ja.md)を参照。

作成日：2026-11-07（日本時間）
modバージョン：`0.3.44-self-owner-id` / ModsAPI：`API_v1.0`（offline全回帰 pass＋11 module checker成功。私有replayは`WOWS_SAMPLING_REPLAY`等で実施）

B46は限定条件（heavy OFF・独立4群ON）で、ユーザー報告 minFPS 約50以上・カクつきなし（録画なし）。1,335 records（active 1,333）、HP平均約2 Hz、比較／damage平均約1 Hz・非due省略、独立 profiler phase を確認。depth／WaveHit／gun は全1,333 available、Battery 272 available／1,061 notSampled。遠距離2 Hz・多数魚雷・全項目の意味保証は未確認。以下の未実機記述は版公開時の履歴。

## 最近の版別到達点（履歴）

- 0.3.44 `self-owner-id`：自艦判定を `owner.isPlayer` から同一 snapshot の `battle.getSelfPlayerInfo().shipId == torpedo.ownerId` へ変更。`owner.isPlayer` は `owner` 行に生の観測値として残すが分類には使わない。`isOwn`・`isOwnSource`・`isOwnReason` を sample 済み行へ公開。自艦は全距離HIGH（敵予算外）、確認済み味方（同一チームかつ `isOwn is False`）は全距離LOW（初観測含む）、敵は半径内の最近 `enemy_high_budget` 本（既定20）だけHIGH。型不一致・self shipId 欠測は `isOwn: null`（unknown）とし味方と誤分類しない。`self.shipId` は毎 sample 新鮮に取得。B50 の観測（`shipId` と `ownerId` が全行厳密一致）を根拠とする。offlineのみ・未実機。
- 0.3.43 `self-id-observation`：自艦 ID と `torpedo.ownerId` の対応を調査するため、`self.identityCandidates` を同一 snapshot に追加。`battle.getSelfPlayerInfo()` から `id`（playerId）と `shipId`、`battle.getSelfPlayerShip()` から公開 `uiId`、および Ship 非公開属性候補 `_Ship__id` / `id` / `vehicleId` を別々の candidate として記録。推測 join・distance heuristic・`isOwn` 上書きは行わず、observer fallback 由来を self と誤記しない。専用 offline 解析ツールとテストを追加。新規設定・probe フラグは不要。実機試験は未実施。
- 0.3.42 `launch-restricted-builtins`：0.3.41 で導入した TTaro Mod Config 連携・魚雷サンプリング設定の正規化ヘルパーへのアクセスに `globals().get(...)` を使用していたため、WoWS Python 2 ランタイムの restricted builtin 名前空間で `NameError` が発生し mod が起動しない障害を修正。`globals()` を直接のモジュールグローバル参照（存在しない場合は `NameError` を捕まえる）に置き換え、restricted builtin（`globals` 欠如）下での `import -> instantiate -> load-complete -> battle -> tick` 実起動経路を回帰テスト追加。TTaro 有無どちらでも core が停止しないことを検証。B49 は 0 byte で無効試験（[記録](docs/VALIDATION_B49_0.3.41_INVALID.ja.md)）。offlineのみ・未実機。
- 0.3.41 `team-torpedo-budget`：魚雷分類へチーム関係と自艦判定を追加。当時は strict `isPlayer is True`の自艦を全距離HIGH（敵予算外）とし、strict同一チームかつ`isPlayer is False`の確認済み味方を全距離LOW（初観測含む）、半径内の敵を最近`enemy_high_budget`本（既定20）だけHIGHとした。0.3.44 では自艦判定を `owner.isPlayer` から `self.shipId == ownerId` へ変更。チーム不明・距離不明・同一チームで自艦不明は安全側HIGH。自作のTTaro Mod Config連携（`ttaro_prefs_adapter.py`＋`ttaro_prefs_binding.py`、schema同梱）をソース登録対応済み（実機パネル表示は未確認）。offlineのみ・未実機。
- 0.3.40 `radius-l5`：魚雷分類半径を`R=L/5`（L=マップ短辺の較正world長）へ正式変更。L/5～L/3帯はLOW、境界上はHIGH、自艦の厳密bool Trueは全距離HIGH、他は近5Hz／遠平均2Hz・5秒再分類を維持。1Hz遠方化ではない。offlineのみ・未実機。
- 0.3.39 `own-torpedo-cadence`：自艦と厳密boolで確認できた魚雷を全距離HIGHに変更。当時の分類半径はL/3。
- 0.3.38 `independent-gun-reload`：gun reload raw を heavy 診断なしで core 周期から採取（既定OFF・collection必須）。装填数・物理管ID・修理timer の意味確定ではない。B46で独立4群の実機可用性確認。
- 0.3.37 `independent-submarine`：自艦 depth／Battery／WaveHit を個別opt-inで診断から独立（既定false・collection必須）。WaveHit対象 namespace／TTL・装填数・管ID は未解決。
- 0.3.36 `damage-cadence`：damage イベント受付を維持し、台帳 snapshot 生成・出力だけを共通1 Hz 枠へ移す。
- 0.3.35 `health-cadence`：共通HP・生存値の取得を平均2 Hz、avatar 照合／集計を1 Hz へ分離。
- 0.3.34 `initial-torpedo-parameters`：魚雷性能・弾薬 params を戦闘ごとの初回結果だけ meta へ保存。
- 0.3.33 `torpedo-sampling-groups`：魚雷を5秒ごとに距離分類し、近距離5 Hz／遠距離平均2 Hz。`torpedoes[]`は今回sampleのみ、membership・sampling状態は `torpedoStatus` で確認。
- 0.3.32：砲弾道計算と専用イベント・`ballistics` 出力を全撤去。
- 0.3.31 `calibration-spatial-index`：較正 reservoir の重複判定を空間 index で絞り込み。B44再生の新旧実装は同値、距離比較94.38%減。

詳細・制約・未確認事項は [TASKS.md](../TASKS.md)、[FPS専用タスク](docs/FPS_TASKS.ja.md)、[既知の問題](docs/KNOWN_ISSUES.ja.md) を参照。

## 最優先：性能報告と安全設定

0.3.14導入後「自艦が沈むまでminFPS 25、撃沈後110まで回復」と報告されています。因果は未確定です。B46（0.3.38・heavy OFF・独立4群ON）ではユーザー報告 minFPS 約50以上・カクつきなしを確認しましたが、今回は魚雷同時最大6本・low群0であり、遠距離2 Hz や多数魚雷時の FPS は未検証です。因果的な改善率・開始直後 FPS 低下も未解明です。

現行ソースは **`0.3.44-self-owner-id`**（offline検証済み・未導入／未実機）。0.3.41 の `team-torpedo-budget` 距離・予算 cadence を維持しつつ、自艦判定を `owner.isPlayer` から同一 snapshot の `battle.getSelfPlayerInfo().shipId == torpedo.ownerId` へ変更。0.3.42 の restricted builtin 修正も維持します。collection/diagnostics/profiler/depth/state/gun reload 独立群はすべて既定OFFです。state は core tick 0.2 秒（約5 Hz、0.1 秒明示で10 Hz互換）を基準とし、各情報群の期限・sample metadata に応じて取得を省略・出力します（同一 `state.json` ファイルに出力されるだけで、すべての項目が毎tick揃うわけではありません）。HP 2 Hz・avatar 比較1 Hz・damage 1 Hz・自艦 depth／Battery／WaveHit／gun reload の独立取得は、明示ON・collection必須で利用可能です。意味・単位・実機 FPS 効果には制約が残ります。通常プレイでは引き続き mod 退避を推奨します。

`config.ini` がない場合・読み込みに失敗した場合も収集停止です。明示的に `collection_enabled = true` のときだけ通常収集を開始します。heavy UI/dataHub probeはさらに `diagnostics_enabled = true`、profilerは独立して `profiler_enabled = true` が必要です。魚雷depth/state samplerはそれぞれ専用opt-inでdiagnostics非依存にできますが、collection opt-inが必須です（全option既定OFF）。intervalは既定・最小1秒、invalid値は1秒へ戻します。同時sampleではheavy/depth/stateのtorpedo collection getter／列挙を共有します。state samplerは`isHoming`/`isSpotted`以外の任意data keyを探索しません。収集停止中はprobe/API poll・定期tickを行わず、戦闘開始時のdisabled stateと終了stateだけを書きます。core収集（既定0.2秒）およびarmament/public_dataの負荷は未評価です。

0.3.7は0.3.6のraw診断を維持し、成功したnamed collectionから完全な単一rowの場合だけweapon／clockの通常観測を別fieldに追加します。0/複数row、partial、truncated、field不明はunknownです。B11では5 collectionすべて単一row、controller `selectedWeapon` 0→2（active開始+21.335秒）、`battleTime` 0→37、`duration` 10を観測し、ユーザー画面報告9:40の選択・数値・操作順との整合を当該試験条件で確認しました。一般条件・サーバー情報としては未保証です。clock残時間は別collectionの同一snapshot観測からのUI式推定で、unit・意味は未検証です。0.3.3配布物・生成物は変更していません。[B11記録](docs/VALIDATION_0.3.6_B11_ROUTES.ja.md)を参照。

0.3.9は`selectedTorpedoParamsProbe`を追加し、B15でUndineの選択TTX 75/9を画面報告と数値照合しました。0.3.10ではGUI owner参照に基づくtooltip parameter raw診断を追加。B18で`playerAvatar` singleton、54 parameter rows、raw `id`/`ownerID`を実機取得し、selectorの複合key exact matchをoffline記録で確認しました。実機再試験は不要です。0.3.11では`submarine_telemetry.py`を追加し、自艦Submarine/BatteryとWaveHitのbounded raw probeを統合。0.3.12ではcollection列挙を`for ... in enumerate(...)`へ変更し、sandboxで`iter`/`next`が名前解決できない場合への互換性を追加しました。実機取得可否・値の意味は未確認です。[短い試験手順](docs/TEST_SUBMARINE_PROBE.ja.md)を参照。

0.3.13ではraw fieldsを保ったまま、静的UI根拠とB27範囲に限定したdepth unit hint、depthIndex/Battery enum label、WaveHit `lifeTime` seconds hintを別`interpretations` metadataに追加しました。サーバー状態一般は確定せず、Battery派生値・depth丸め・`maxLifeTime`計算もありません。同じ潜水テストの再要求は不要です。[正本とB27記録](docs/RESEARCH_SUBMARINE_STATE_SEMANTICS.ja.md)を参照。

0.3.14-identity-depth-candidatesまでの以下の機能は開発履歴です。0.3.15の既定では収集停止となり、出力されません。`uiTorpedoProbe.rows[].depth`と`torpedoes[].uiState.depth`に、有限数値だけのread-only depth候補を追加（0保持、`position.y`代用・前frame持越しなし）。さらに`identityCandidates`として、同じsnapshotの`ships[].vehicleId`と魚雷`ownerId`／WaveHit`targetID`の厳密scalar値一致候補を別出力します。候補はAPI契約ではなく、`matchStatus`と`completeness=unknown`を分離し、0件一致は`indeterminate`、複数は`ambiguousMultiple`（最大8候補）、単一`targetShipId`は出しません。legacy`isOwn`／`owner`／`targetID`は上書きしません。B10/B12/B14はself-only、B27は敵1 targetのoffline根拠に限定し、現在のships列挙完全性は不明のままです。0.3.13の`interpretations` raw/metadataは変更しません。[ID名前空間調査](docs/RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md)を参照。専用の実機試験は追加せず、次回の通常魚雷発射時にdepth候補を相乗り確認します。

オフライン全回帰：`python -m pytest -q`。ゲーム上の潜水艦probe取得可否・意味は実機未検証です。導入・manifest/ZIPは親セッションが管理します。

全体目標は、潜水艦向け外部2Dマップ用modを完成させ、魚雷戦に必要なすべての情報を出力することです。AIが試験を指示・解析し、ユーザーがMeatProxyとして実機操作・記録を担当します。[目標・残課題](../TASKS.md)を参照してください。

元仕様と実機取得状況の最新版：[詳細対応表](docs/SPEC_COVERAGE_0.3.1.ja.md)。

**簡易2Dマップ**：`launch-map.bat` をダブルクリック。実際に起動したbuildを自動検出して読みます。
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

**15.10クライアント（現行 build 13533378）の訓練戦で実機確認を進めています。** ATM状態はdataHubから直接読み取り、
isHoming/isSpottedを取得します。UI→Flash→Pythonの橋渡しは使用していません。
12対12・別地図・失探時の鮮度は未検証です。外部表示のグリッドとゲーム内位置は概ね一致すると目視確認済みですが、定量誤差・全条件の検証ではありません。

## まずやること

1. ゲームを終了し、既存の `res_mods/PnFMods/WowsExtractor` と `PnFModsLoader.py` をバックアップします。ATMあり環境で `install.bat` を使う場合（実際の導入先buildは起動buildから自動検出）、既定ではATM本体とATM専用unboundは自動で退避されます。ATMを残したままcollectorだけを入れる場合は、明示的に `--with-atm`（PowerShellでは `-WithAtm`）を付けます。どちらの場合も `TTaroModUtils` と `PnFModsLoader.py` は動かしません（詳細は [自動検出インストーラー](docs/INSTALL_BAT.ja.md)）。
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
                ├─ submarine_telemetry.py
                ├─ map_calibration.py
                ├─ performance_profiler.py
                └─ config.example.ini
```

`config.example.ini` は必要なら `config.ini` にコピーします。未作成なら収集停止です。`Main.py` 単体では動きません。

導入に必要なPython sourceは11 filesです：`Main.py`, `battle_identity.py`, `damage_tracker.py`, `emit_guard.py`, `ui_health.py`, `torpedo_telemetry.py`, `submarine_telemetry.py`, `map_calibration.py`, `performance_profiler.py`, `ttaro_prefs_adapter.py`, `ttaro_prefs_binding.py`。任意でTTaro Mod Config schema `res_mods/ModSchemas/kitta-wows-extractor.schema.json` を同梱します。installerの明示allowlistと`tools/check_collector_offline.py`の必須module listを同期しています。offline確認は対応するPython 3.10–3.12で`python tools/check_collector_offline.py`、回帰は`python -m pytest -q`。manifest/checksumは`tools/build_bundle.py`で再生成します。

## この版でできること

- 可視魚雷の公開7属性、発射元の公開属性、味方／敵の整理情報を出力。
- 自艦の発射管状態、選択魚雷弾ID、APIが返す場合の公開弾パラメーターを出力。
- `weaponHubProbe`にUI由来のweaponSlot/progress/ammo/serialLoad候補を最大32件ずつ read-only 診断（実機未確認、意味未確定）。
- `weaponContextProbe`と`gameClockProbe`でcontext／clock候補を独立してread-only診断（実機未確認、候補別statusを確認）。
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
| [自動検出インストーラー](docs/INSTALL_BAT.ja.md) | 起動buildを自動検出。ATM自動退避と復元を含む |
| [出力仕様](docs/OUTPUT_SPEC.ja.md) | 全トップレベル項目、魚雷関係全フィールド、欠損値、単位、例 |
| [B41供給元調査](docs/RESEARCH_B41_MOD_DATA_PRODUCER.ja.md) | mods_DataComponentの供給元限界と0.3.30の明示provider方針 |
| [opt-in性能計測計画](docs/PLAN_PERFORMANCE_PROFILING.ja.md) | 0.3.20 profiler、時計候補、集計境界と未確認事項 |
| [性能問題記録](docs/PERFORMANCE_INCIDENT_0.3.14.ja.md) | FPS報告・安全措置・未評価領域 |
| [元仕様との詳細対応表](docs/SPEC_COVERAGE_0.3.1.ja.md) | 取得済み・条件付き・推定・未取得を項目別に整理 |
| [外部簡易2Dマップ](docs/SIMPLE_MAP.ja.md) | localhost起動、マーカー、更新停止・終了時の表示 |
| [実機テスト手順](docs/TEST_PLAN.ja.md) | `type`最優先、ATMなし／あり、1ping／2ping、終了・再入場 |
| [context／clock試験](docs/TEST_CONTEXT_CLOCK.ja.md) | Minotaurの魚雷単発・再装填と戦闘残時間の確認 |
| [潜水艦probe短時間試験](docs/TEST_SUBMARINE_PROBE.ja.md) | Undineの深度/Battery、任意のping観測 |
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
- `isHoming/isSpotted` はATM等の供給に依存し、取得不可はnullです。nullや項目欠落はfalseではありません。0.3.30では`torpedo_state_provider=advanced_torpedo_marker`を明示した場合だけATM由来の導出値として区別し、`isSpotted`は推定・第三者判定、`isHoming`も第三者判定で、ゲーム／サーバーの生状態を保証しません。
- ファイルは毎回上書きされます。**戦闘終了後の `state.json` だけでは戦闘中の変化は残りません。** 履歴記録を推奨します。

## 出自・ライセンス

ベース：[Tz-WIND/8111_for_wows](https://github.com/Tz-WIND/8111_for_wows)、コミット `28470b6ff0c05bac8aa41bd7d986daa6814242e2`。元プロジェクトのクライアント側に魚雷出力を追加しています。
このパッケージは独立した公式リリースではありません。ATM本体・署名済みAPI v2ファイル・第三者の画像等は再配布していません。
MITライセンス。原著作権表示を含む [LICENSE](LICENSE) を同梱しています。

`SHA256SUMS.txt` は収録ファイルのチェックサムです。配布者本人を証明する電子署名ではありません。
