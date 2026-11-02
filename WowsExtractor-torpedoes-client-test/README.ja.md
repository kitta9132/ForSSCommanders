# WowsExtractor 魚雷出力版：実機テスト用パッケージ

作成日：2026-11-02（日本時間）
modバージョン：`0.3.21-position-read-budget` / ModsAPI：`API_v1.0`（source only・未導入）

## 最優先：性能報告と安全設定

0.3.14導入後「自艦が沈むまでminFPS 25、撃沈後110まで回復」と報告されています。外部記録ツールは未使用とのことですが、mod内部のtick・state書込は別途戦闘中継続します。因果は未確定です。0.3.21はsource only・未導入です。`collection_enabled = false`、`diagnostics_enabled = false`、`profiler_enabled = false`、`position_fallbacks_enabled = false`の既定を維持します。coreでは艦本体の`getPosition`を一回だけ読み、同frame player lookupを位置処理で再実行しません。重い互換fallbackは専用opt-inかつdiagnostic due時だけです。過去fallback-only経路の位置が通常tickで未取得になり得ます。FPS改善・実機安全確認済みとは主張しません。writer thread時間、FPS、API内部時間は未計測です。通常プレイには収集modのロード対象外への退避を推奨します。詳細：[性能事故記録](docs/PERFORMANCE_INCIDENT_0.3.14.ja.md)／[B28調査](docs/RESEARCH_SHIP_COLLECTION_B28.ja.md)

`config.ini` がない場合・読み込みに失敗した場合も収集停止です。明示的に `collection_enabled = true` のときだけ通常収集を開始します。重いUI/dataHub probeはさらに `diagnostics_enabled = true`、profilerは独立して `profiler_enabled = true` が必要です（どちらもcollection必須）。収集停止中はprofiler初期化clock callも0回で、probe/API poll・定期tickを行わず、戦闘開始時のdisabled stateと終了stateだけを書きます。core収集（0.1秒）およびarmament/public_dataの負荷は未評価です。

0.3.7は0.3.6のraw診断を維持し、成功したnamed collectionから完全な単一rowの場合だけweapon／clockの通常観測を別fieldに追加します。0/複数row、partial、truncated、field不明はunknownです。B11では5 collectionすべて単一row、controller `selectedWeapon` 0→2（active開始+21.335秒）、`battleTime` 0→37、`duration` 10を観測し、ユーザー画面報告9:40の選択・数値・操作順との整合を当該試験条件で確認しました。一般条件・サーバー情報としては未保証です。clock残時間は別collectionの同一snapshot観測からのUI式推定で、unit・意味は未検証です。0.3.3配布物・生成物は変更していません。[B11記録](docs/VALIDATION_0.3.6_B11_ROUTES.ja.md)を参照。

0.3.9は`selectedTorpedoParamsProbe`を追加し、B15でUndineの選択TTX 75/9を画面報告と数値照合しました。0.3.10ではGUI owner参照に基づくtooltip parameter raw診断を追加。B18で`playerAvatar` singleton、54 parameter rows、raw `id`/`ownerID`を実機取得し、selectorの複合key exact matchをoffline記録で確認しました。実機再試験は不要です。0.3.11では`submarine_telemetry.py`を追加し、自艦Submarine/BatteryとWaveHitのbounded raw probeを統合。0.3.12ではcollection列挙を`for ... in enumerate(...)`へ変更し、sandboxで`iter`/`next`が名前解決できない場合への互換性を追加しました。実機取得可否・値の意味は未確認です。[短い試験手順](docs/TEST_SUBMARINE_PROBE.ja.md)を参照。

0.3.13ではraw fieldsを保ったまま、静的UI根拠とB27範囲に限定したdepth unit hint、depthIndex/Battery enum label、WaveHit `lifeTime` seconds hintを別`interpretations` metadataに追加しました。サーバー状態一般は確定せず、Battery派生値・depth丸め・`maxLifeTime`計算もありません。同じ潜水テストの再要求は不要です。[正本とB27記録](docs/RESEARCH_SUBMARINE_STATE_SEMANTICS.ja.md)を参照。

0.3.14-identity-depth-candidatesまでの以下の機能は開発履歴です。0.3.15の既定では収集停止となり、出力されません。`uiTorpedoProbe.rows[].depth`と`torpedoes[].uiState.depth`に、有限数値だけのread-only depth候補を追加（0保持、`position.y`代用・前frame持越しなし）。さらに`identityCandidates`として、同じsnapshotの`ships[].vehicleId`と魚雷`ownerId`／WaveHit`targetID`の厳密scalar値一致候補を別出力します。候補はAPI契約ではなく、`matchStatus`と`completeness=unknown`を分離し、0件一致は`indeterminate`、複数は`ambiguousMultiple`（最大8候補）、単一`targetShipId`は出しません。legacy`isOwn`／`owner`／`targetID`は上書きしません。B10/B12/B14はself-only、B27は敵1 targetのoffline根拠に限定し、現在のships列挙完全性は不明のままです。0.3.13の`interpretations` raw/metadataは変更しません。[ID名前空間調査](docs/RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md)を参照。専用の実機試験は追加せず、次回の通常魚雷発射時にdepth候補を相乗り確認します。

オフライン全回帰：`python -m pytest -q`。ゲーム上の潜水艦probe取得可否・意味は実機未検証です。導入・manifest/ZIPは親セッションが管理します。

全体目標は、潜水艦向け外部2Dマップ用modを完成させ、魚雷戦に必要なすべての情報を出力することです。AIが試験を指示・解析し、ユーザーがMeatProxyとして実機操作・記録を担当します。[目標・残課題](../TASKS.md)を参照してください。

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
12対12・別地図・失探時の鮮度は未検証です。外部表示のグリッドとゲーム内位置は概ね一致すると目視確認済みですが、定量誤差・全条件の検証ではありません。

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
                ├─ submarine_telemetry.py
                ├─ map_calibration.py
                ├─ performance_profiler.py
                └─ config.example.ini
```

`config.example.ini` は必要なら `config.ini` にコピーします。未作成なら収集停止です。`Main.py` 単体では動きません。

導入に必要なPython sourceは9 filesです（0.3.20）：`Main.py`, `battle_identity.py`, `damage_tracker.py`, `emit_guard.py`, `ui_health.py`, `torpedo_telemetry.py`, `submarine_telemetry.py`, `map_calibration.py`, `performance_profiler.py`。installerの明示allowlistと`tools/check_collector_offline.py`の必須module listを同期しています。offline確認は対応するPython 3.10–3.12で`python tools/check_collector_offline.py`、回帰は`python -m pytest -q`。manifest/checksumは生成物で、今回更新せず親セッション管理です。

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
| [バージョン固定インストーラー](docs/INSTALL_BAT.ja.md) | build 13357625用。ATM自動退避と復元を含む |
| [出力仕様](docs/OUTPUT_SPEC.ja.md) | 全トップレベル項目、魚雷関係全フィールド、欠損値、単位、例 |
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
- `isHoming/isSpotted` はATM等の供給に依存し、取得不可はnullです。nullや項目欠落はfalseではありません。
- ファイルは毎回上書きされます。**戦闘終了後の `state.json` だけでは戦闘中の変化は残りません。** 履歴記録を推奨します。

## 出自・ライセンス

ベース：[Tz-WIND/8111_for_wows](https://github.com/Tz-WIND/8111_for_wows)、コミット `28470b6ff0c05bac8aa41bd7d986daa6814242e2`。元プロジェクトのクライアント側に魚雷出力を追加しています。
このパッケージは独立した公式リリースではありません。ATM本体・署名済みAPI v2ファイル・第三者の画像等は再配布していません。
MITライセンス。原著作権表示を含む [LICENSE](LICENSE) を同梱しています。

`SHA256SUMS.txt` は収録ファイルのチェックサムです。配布者本人を証明する電子署名ではありません。
