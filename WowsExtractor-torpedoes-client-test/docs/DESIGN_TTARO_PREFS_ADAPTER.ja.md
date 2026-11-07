# TTaro Mod Config 名前登録・設定adapter設計（0.3.41系・新規追加）

本書は新規追加分のみを扱う設計メモ（自作担当＝kitta/MiMo）。Main・torpedo_telemetry・既存tests/docsはDS側担当のため編集していない。対象承認方針：「まずTTaro Mod Configに名前登録をして、今後追加する要素は設定で変更可能にする設計」。

## 成果物（この版で追加したファイル）

| ファイル | 役割 |
| --- | --- |
| `res_mods/ModSchemas/kitta-wows-extractor.schema.json` | TTaro Mod Config用の完全自作schema（名前登録＋新設定2件） |
| `res_mods/PnFMods/WowsExtractor/ttaro_prefs_adapter.py` | 自作optional prefs adapter（Python 2/3両用・ゲーム未導入） |
| `tests/test_ttaro_prefs_adapter.py` | 新規stub tests（notification/dedup/pending/invalid/unsubscribe/absent/Python2 grammar/schema契約） |
| `docs/DESIGN_TTARO_PREFS_ADAPTER.ja.md` | 本書 |

既存のinstaller・offline checker・Main・torpedo_telemetry・SHA256SUMS・既存docsは変更していない（統合はDS側。下記「DS統合依頼」参照）。

## 登録方式と前調査の根拠

- 実機（build 13533378）の `res_mods/ModSchemas/` をread-onlyで調査。TTaroModUtils `SchemaScanner.py` が起動時に `*.schema.json` を走査し、必須fieldは `schemaVersion / id / author / modName / slug / tree`。`schemaVersion` は整数でMIN 4。`id` はpath文字を含まない一意な文字列（重複idは両方拒否）。`author` は小文字英数字・先頭英字・予約名（registry/installedMods/framework/uiState/dragState）以外。`slug` はドット無し。以上の検証を自前で再現するtestを用意した。
- 公式README（AndrewTaro/TTaroModUtils）の注意：「ModSchemasの各ファイルは作者のconfig tool生成物。編集するな、**他のmodへコピーするな**（id再利用で両方の設定が拒否される）」。→ 既存schemaの流用は禁止と判断し、id/author/構造とも完全自作のschemaを新規作成した。id `kwxconfigkitta20260001` は既存ttaro系idと衝突しない新規発行。
- license前調査：TTaroModUtils / TTaroModConfig / ModForge のGitHub公開リポジトリに**LICENSE file無し**（＝デフォルトで再利用許諾なし）。したがって第三者コード（Hub系/難読化内部）のコピー・改変・既存mod/作者APIの改変は一切行わず、本schema・adapterは仕様観察のみから自作した。adapterはTTaroModUtilsをimportしない。
- 新author登録の可否：frameworkの仕組み上、author文字列に中央登録ゲートは無く（SchemaScannerが文字規約のみ検証）、`kitta` は既存 `ttaro` と非衝突。ただし第三者schemaの利用が作者に公式許諾されているかは未確認。**強制登録は行わず、schema候補としてrepoに追加したにとどまる**（「使用許可が必須で登録不可なら無理せずschema候補＋未登録報告」に従う）。実パネル表示は次回ゲーム起動でのみ検証可能で未確認。

## 登録状態の区分（重要）

- **実施済み：実ファイル追加のみ**（repo内 `res_mods/ModSchemas/` へ自作schemaを配置）。
- **未実施：実機panel表示未確認**。schema scanは起動時（`Framework.start()`）なので、反映確認には実ゲームの次回読込が必要。現時点でゲームへの導入は行っていない（導入はメインエージェントの既存手順・禁止事項に従う）。
- runtime購読API（`CC.mods_DataComponent` の `evDataChanged` をPythonから購読できるか）も未検証。GUI `Components.xml` は `mods_DataComponent` の `id/data/evDataChanged` 定義を確認済み（B41調査）だが、Python側のイベント登録方法は未確認。そのためadapterは購読をinjected bindingに委ね、実game bindingは後付け可能な設計にした。

## schema内容（名前登録＋新設定2件のみ）

- `modName: "WowsExtractor"`（パネルにまず名前が表示される）、`author: "kitta"`、`slug: "wows-extractor"`、`id: "kwxconfigkitta20260001"`、`order: 100`。
- 設定は新規2件のみ。既存config.iniの全キーは今回公開しない（方針：今後追加する要素を順次設定化する）。
  - `enemyHighBudget`（slider、default 20、range 1–64、step 1、decimals 0）＝敵魚雷high予算（torpedo_telemetry `SAMPLING_ENEMY_HIGH_BUDGET = 20` に対応）。
  - `radiusDivisor`（slider、default 5、range 2–10、step 0.5、decimals 1）＝near/high半径 `min(mapW,mapH)/divisor`（`SAMPLING_RADIUS_DIVISOR = 5.0` に対応）。
- label/hintは平文。ttaro標準のIDS_* phrase解決を経由しないため、実機での描画（平文labelがそのまま出るか）は未確認。`Migrations/kitta-wows-extractor.migrations.json` は不要（migrationVersion 0相当・store version 0でlockされない）。

## adapter設計（ttaro_prefs_adapter.py）

- **依存はoptional**。TTaro Mod Config不在（binding無し／購読不能）時はini fallback値を使い `source()` が `'ini'`、framework値を受信したら `'ttaro'`。fallbackも無い場合は既定値で `'none'`。
- **イベントcallbackはpending純値のみ**。`notify(key, value)` は純scalar（bool/数値/文字列）だけをpendingへ記録（最新値優先）。dict・list・API object等は即座に `nonPureValue` 拒否し、pendingに生きたオブジェクトを保持しない。UIアクセス・状態適用はcallback内では行わない。
- **tickでconsume_pending／revision適用**。適用は `tick()` のみ。pendingを検証・適用し、変更が1件以上あれば `revision` を1回だけ加算。同一値の再通知はdedupでrevision不変。collectorは自分のframeの安定した時点で設定を観測できる。
- **厳密validation**：unknown keyは拒否。数値keyへbool・非数値・非有限（NaN/Inf）はinvalidで**現値維持**。有限数値はschema安全rangeへ**clamp**。int key（enemyHighBudget）へ非整数floatはinvalidで現値維持。invalid入力が状態へ入ることは無い。framework側 `Validate.py` もclamp＋step丸めだが、adapter側は独立に厳密検証する（二重防御）。
- **購読handleのframe間保持は明示的に許可**（telemetryのlive object禁止とは別責務）。handleは `(setting_key, handle)` の明示listで保持し、mod unload／battle endの `stop(reason)` で**各handle一度だけ**解放（冪等・共有handle objectは一度のみ・subscribe失敗時のNone handleは解放対象外）。次battleの `start()` で再購読。
- **registry rebinding**：framework reload/rebindでcomponent再生成→stale handleの可能性。`rebind(binding)` は旧handleを全解放して再購読（実行中でなければbinding差替のみ）。再購読失敗はsurviveしhandle listに追跡。
- **collection停止中のライフサイクル・全キーUI公開は今回scope外**。将来拡張の方向のみ：collection_enabled=false中はadapter tickを止め、無効化中の設定変更をbattle開始時に取り込む案を残す（未設計・未実装）。

## DSへ渡す公開interface（契約）

- schema path：`res_mods/ModSchemas/kitta-wows-extractor.schema.json`
- module path：`res_mods/PnFMods/WowsExtractor/ttaro_prefs_adapter.py`（import名 `ttaro_prefs_adapter`、トップレベルgame import無し）
- shape keys / default values / safe range（単一の真実＝`SETTING_SPECS`）：

| schema key | contract key（ini/telemetry） | kind | default | min | max |
| --- | --- | --- | --- | --- | --- |
| `enemyHighBudget` | `enemy_high_budget` | int | 20 | 1 | 64 |
| `radiusDivisor` | `radius_divisor` | float | 5.0 | 2.0 | 10.0 |

- DataHub component名：`modPrefs.kitta.enemyHighBudget` / `modPrefs.kitta.radiusDivisor`（`component_key()` で導出）。
- API（`PrefsAdapter`）：
  - `PrefsAdapter(binding=None, fallback=None, log=None)` — bindingは `subscribe(component_key, callback)->handle` / `unsubscribe(handle)` / 任意 `read(component_key)->raw` を持つduck type。fallbackは `fallback_from_config(cfg)` でini dictから生成。
  - `start()` → source token（`'ttaro'|'ini'|'none'`）。購読開始＋ini fallback適用。
  - `tick()` → 適用件数（0以上）。consume_pending＋revision。
  - `values()` / `value(contract_key)` / `revision()` / `source()` / `status()` / `rejected()` / `handles()`。
  - `notify(key, value)` / `notify_many(dict)` — 純値通知（event callbackターゲット）。
  - `stop(reason)` → 解放handle数（`'battleEnd'` / `'modUnload'`）。`rebind(binding=None)`。
  - モジュール定数：`SETTING_SPECS` / `DEFAULTS` / `SPEC_BY_KEY` / `SPEC_BY_CONTRACT` / `MOD_AUTHOR` / `MOD_SLUG` / `MOD_ADDR` / `SCHEMA_RELPATH` / `coerce_value()` / `component_key()` / `fallback_from_config()`。
- DS側接続イメージ：Mainのframe/tickから `adapter.tick()` を呼び、変更時 `values()['enemy_high_budget']` / `values()['radius_divisor']` をtorpedo_telemetryのsampling設定（現行定数 `SAMPLING_ENEMY_HIGH_BUDGET` / `SAMPLING_RADIUS_DIVISOR` 相当の引数）へ反映する。torpedo_telemetryの `TorpedoSamplingScheduler` は既に `enemy_high_budget=` 引数を持つので、契約変更は引数供給側のみのはず（要DS確認）。

## DS統合依頼（installer/manifest・今回scope外）

現installer `install-wowsmod.ps1` はcollector 9 py（Main/battle_identity/damage_tracker/emit_guard/ui_health/torpedo_telemetry/submarine_telemetry/map_calibration/performance_profiler）を固定copyし、`tests/test_installer.py` も同listを検証。新module/schemaの同梱はDSが統合する。追加分一覧：

1. `res_mods/PnFMods/WowsExtractor/ttaro_prefs_adapter.py`（PythonFiles listへ10本目として追加）
2. `res_mods/ModSchemas/kitta-wows-extractor.schema.json`（installerのcopy対象＋hash対象へ。ModSchemas新規folder）
3. `tools/check_collector_offline.py` のchecker対象module listへ `ttaro_prefs_adapter`（現9 module checkerを10に）
4. `SHA256SUMS.txt` 再生成と `tests/test_installer.py` のlist更新
5. Main.pyからのadapter呼び出し（`start/tick/stop('battleEnd')/stop('modUnload')`）とtorpedo_telemetry引数反映（上記契約）
6. `config.example.ini` へ任意のini fallbackキー例（`enemy_high_budget = 20` / `radius_divisor = 5.0`）— ini fallbackはTTaro absent時のみ使用。schema優先。

## テスト結果（実施済み・オフライン）

- `tests/test_ttaro_prefs_adapter.py`：**22 passed**（Python 3.14.7）。Python 3.11でも22 passed（lib2to3によるPython 2 grammar parse経路を実行。3.13+ではlib2to3欠落のためtoken走査のみに自動フォールバック）。
- 既存全tests：**exit 0**（fail/error無し、skipは既存どおり）。
- カバレッジ：notification純値／pending遅延適用／dedup（同値・重複通知）／invalid（bool・非整数・NaN・Inf・文字列→現値維持）／unknown key拒否／clamp／unsubscribe一度きり＋冪等／battle endとmod unload両方／registry rebinding（stale handle解放・再購読・失敗時survive）／TTaro absent→ini fallback（無効fallbackは既定維持・ini→ttaro切替）／初期readがpendingのみ／Python 2 grammar（ASCII・f-string/アノテーション/walrus/async禁止・py2 builtin名経路）／schema↔adapter契約（keys/defaults/range/prefix衝突/author規約）。

## 未確認・制約（実機で確認するまで断定しない）

- 実機panel表示（modName「WowsExtractor」とslider 2件の描画・操作・保存）は未確認。schema scanは起動時なので次回ゲーム読込が必要。
- 平文label/hintの実際の描画（IDS_*未定義phraseのfallback挙動）は未確認。
- Pythonからの `evDataChanged` 購読方法・persist先（`(wows)/ModPrefs/<id>.json`）の実挙動は未確認。現adapterはbinding注入で購読経路を差し替え可能にしている。
- frameworkのhot reload（`ttModConfig.hotReloadEnabled`）との組合せは未試験。`rebind()` で対応する設計だが実機未確認。
- 導入・実機操作は行っていない（登録は「実ファイル追加のみ」）。

## 追記：DS統合完了（0.3.41 実装・2026-11-07）

上記はMiMo自作分の設計メモである。以下はその後の統合で確定した事項のみを追記する（本文は履歴として保持）。

- **登録方針の確定**：ユーザー承認により、独自schema（`kitta-wows-extractor.schema.json`）を**正本配布に同梱**し、installerで`res_mods\ModSchemas`へ**明示配置**する。schema中央登録gateは無く文字規約のみ（`kitta`は予約語でない）。公式第三者サポート／実機panel表示は引き続き**未確認**（「ソース登録対応済み／実機表示未確認」を区別する）。
- **追加module（11本目）**：自作bridge `res_mods/PnFMods/WowsExtractor/ttaro_prefs_binding.py`。adapter binding契約（`subscribe`/`unsubscribe`/`read`）を実装し、provider seam（`set_binding_provider`/`get_binding_provider`）と、標準dataHub読み取り面（`getSingleEntity('userPrefs')`→`entity._Entity__hub`→`getEntityByIndex(key, UiComponents.mods_DataComponent)`→`entity.mods_DataComponent`）のみを使う既定resolverを持つ。**1キーにつき1回のindexed lookupのみで、設定の全列挙はしない**。TTaroModUtils/ModForgeのコードはimport・コピーしない（難読化consumerの読み取り面を観察して再実装）。
- **Main統合**：`Main.py`は`_ensure_torpedo_prefs_adapter`でadapterを一度だけ生成し、`events.onLoadModsCompleted`（`_on_load_mods_completed`）でbindingを解決・購読する。battle開始で再bind、battle終了／unloadで`dispose_torpedo_prefs_adapter`が購読を解放する。`_tick`冒頭で`_consume_torpedo_prefs(now)`→`_apply_pending_torpedo_sampling_settings(now)`→frame構築の順に適用する。framework不在時はbindingが`None`となりini fallbackのまま（absence fallback）。
- **clamp分離**：`coerce_value(setting_key, value, clamp=True)`。UI入力は`clamp=True`（UI安全範囲1–64／2.0–10.0）、ini fallbackは`clamp=False`で**広いini値を狭いUI範囲へ丸めない**。
- **installer／checker／manifest**：`install-wowsmod.ps1`のPythonFilesは11本（adapter＋binding）、schemaは`$script:SchemaFiles`でallow-list配置（他のschemaは触らない。同一名が既存で内容が異なる場合は`ModSchemas_*`へ退避してから差替、失敗時rollback）。`tools/check_collector_offline.py`の想定moduleは11本。`SHA256SUMS.txt`は`tools/build_bundle.py`で再生成する。
- **テスト**：`tests/test_ttaro_prefs_adapter.py`（22）、`tests/test_ttaro_prefs_binding.py`、`tests/test_ttaro_prefs_integration.py`（Main⇔bridgeライフサイクル・absence fallback・tick順序）を追加。installer testsにschema配置／no-overwriteを追加。
