# 0.3.9 B15 選択魚雷TTX診断の実機確認

## 結論

- 対象は `recordings/without-atm-b15.jsonl`。modは`0.3.9-torpedo-ttx-diagnostics`。1 meta + 163 state（通常162、終了1）を1行ずつJSON parseして集計し、全行を一括でJSON配列化・表示していない（SHA-256算出時のみバイト列を読んだ）。parse error 0、末尾改行あり。読み取り前後のstatは同一で、解析時点の書込み進行は観測されなかった。
- `selectedTorpedoParamsProbe` の選択経路は162通常stateすべてでstrict一意match。descriptorは`pinger` 25 state（JSONL行1–25）から`torpedo` 137 state（行26–162）へ遷移した。`reason`は全state nullで、`incomplete` / `nonUnique` / `noMatch` は0。probeを信用せず、controller selected raw・slot type・slot/ammo id・viewData descriptorを同じ条件で独立に再照合しても162/162一致し、probeとの不一致は0だった。
- `selfVehicle` collection/component/`shipTTX`は162/162でavailable。固定3 variantのうち`torpedo`は162/162でavailable、`torpedo_deepwater`と`torpedo_alternative`は162/162で`none`。このためTTX route集約の`ttxStatus`は全state `partial`だが、これは**選択variantやspeed/maxDistの取得失敗ではない**。選択された`torpedo` variantは137/137で`variantStatus=available`、`leafStatus=available`。
- 選択`torpedo` variantのFloatDiff実測は、`speed.value=75.0`（float, available）、`speed.delta=0`（int, available）、`maxDist.value=9.0`（float, available）、`maxDist.delta=0`（int, available）。137選択stateすべて同値。選択されていないpinger区間を含む全162 stateでも、固定`torpedo` variant自体は同じ75.0/9.0でavailableだった。
- ユーザー報告の画面表示「75kts/9km」は、当該Undine条件の静的TTX表示候補raw `75.0` / `9.0`と数値上一致する。これはユーザーの独立目視根拠として扱う。ただし確認できたのは**静的TTX表示候補の整合**であり、補正後live速度・最大射程、艦長スキル等の反映、Battle tooltipのalternative parameter上書き、単位の確定ではない。deltaは加算せず、kmからmへの変換もしていない。
- B15の`torpedoArmament.ammoParams`は通常162 stateすべて`{}`（`ammoParamsStatus=available`）。今回の75/9は`getAmmoParams` / `ammoParams`経由ではなく、`viewData.paramsDescriptor`で選んだ`shipTTX.torpedoes.torpedo`経由である。両者を同一取得経路として扱わない。
- 個人名・player ID・battle ID・entity/ammo実IDは本メモへ転記しない。

## 入力と完全性

- 対象：`WowsExtractor-torpedoes-client-test/recordings/without-atm-b15.jsonl`。
- stat（解析前＝解析後）：size `7,862,263` bytes、mtimeNs `1793563628504014000`。SHA-256 `5f6efa79ebe9f538ae30cbb8bb470a42b3f79494b272cbe2a43d9dedf0944182`。
- 全164行：meta 1、state 163、parse error 0、末尾改行あり。stateは通常形162と、`active:false`の軽量終了形1。
- meta：mod `WowsExtractor` / `0.3.9-torpedo-ttx-diagnostics`、`TrainingBattle`、`GAMEMODE_AWESOME`。`ts`はゲーム由来でUnix時刻ではないため、順序確認だけに使う。
- 通常stateの`ts`範囲は約`126.5755`–`143.3334`。最終行163は`ts=143.4271`、`active:false`で、probe/weapon/clock系を含まない終了用軽量schema。これを空観測やprobe失敗として数えない。
- 参照実装：`res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py` の`selected_torpedo_params_probe`（1115–1302行）と`safe_selected_torpedo_params_probe`（1305–1315行）、`Main.py`のstate組立（1249–1274行）。参照仕様：`docs/OUTPUT_SPEC.ja.md`「selectedTorpedoParamsProbe」（207–218行）、`docs/RESEARCH_SELECTED_TORPEDO_PARAMS.ja.md`。

## 段階statusと選択

| 項目 | 値 | state数 |
| --- | --- | ---: |
| top-level `status` | `available` / `notApplicable` | 137 / 25 |
| `selection.status` | `available` / `notApplicable` | 137 / 25 |
| `selection.reason` | null | 162 |
| `selection.descriptor` | `torpedo` / `pinger` | 137 / 25 |
| `stages.selection` | `available` / `notApplicable` | 137 / 25 |
| `selfVehicle.status` | `available` | 162 |
| `selfVehicle.collectionStatus` | `available` | 162 |
| `selfVehicle.componentStatus` | `available` | 162 |
| `selfVehicle.shipTTXStatus` | `available` | 162 |
| `stages.selfVehicle` | `available` | 162 |
| `stages.shipTTX` | `available` | 162 |
| `stages.variants` = `ttxStatus` | `partial` | 162 |
| `stages.variant` / `variantStatus` | `available` / `unknown` | 137 / 25 |
| `stages.leaf` / `leafStatus` | `available` / `unknown` | 137 / 25 |

- descriptor遷移は行1–25が`pinger`、行26–162が`torpedo`。pinger区間のtop-levelは設計どおり`notApplicable`で、`variantStatus`/`leafStatus`は`unknown`。これはpinger用TTX variantを選択しないための状態であり、`selfVehicle`/`shipTTX` routeの失敗ではない。pinger区間でも`stages.variants`は`partial`のまま残る。
- 固定variantの内訳：`torpedo` available 162、`torpedo_deepwater` none 162、`torpedo_alternative` none 162。`ttxStatus=partial`は、3候補のうち2候補が存在しないことによる集約値である。選択variantの親statusとspeed/maxDist leaf statusは別に確認した。

## FloatDiffの実測

選択`torpedo` variant（137 state）の集計。値はrawで、単位・意味は`semantics=unverified`。

| field | value | value type/status | delta | delta type/status | unitHint |
| --- | ---: | --- | ---: | --- | --- |
| `speed` | 75.0 | float / available | 0 | int / available | knots (TTX UI) |
| `maxDist` | 9.0 | float / available | 0 | int / available | km (TTX UI) |

- 137/137 stateで4つのleaf（speed.value、speed.delta、maxDist.value、maxDist.delta）がすべてavailable。`leafStatus`も137/137 available。
- 未選択のpinger区間を含む全162 stateの固定`torpedo` variantでも、speed/maxDistのvalue/deltaは同じ75.0/0、9.0/0でavailable。variant値は選択状態に依存しない静的TTX候補として観測された。
- deltaは0だったが、値を補正・合成する根拠にはしない。`speed.value + speed.delta`等の加算、km→m変換、表示丸めの再現は行っていない。

## 画面報告との限定照合

- ユーザー報告「75kts/9km 15b 不具合なし」のうち、本probeが直接照合できるのは速度と最大射程。画面の75kts/9kmは、当該条件の`shipTTX.torpedoes.torpedo` raw 75.0/9.0と一致する。これはログ単独ではなく、実機画面を見たユーザーの独立根拠を加えた当該Undine条件内の整合である。
- 「15b」は本probeの項目へ対応づけず、意味を推測しない。今回の数値整合・status確認の対象外とする。
- 「不具合なし」もユーザー目視の報告として扱う。B15では当該経路のstatus/値に失敗を示す段階は見つからないが、ゲーム全体・他艦・他条件で不具合がないことの証明にはしない。
- 分離して扱う未確認点：補正後live速度/最大射程、艦長スキルやmodifierの反映、Battle tooltipの代替parameter上書き、TTXの単位・deltaの表示意味、実魚雷motionとの対応。`displaySemantics`も`speed`は`staticTTXDisplayCandidate`、`liveAdjusted=false`、`battleTooltipAlternativeOverridePossible=true`であり、補正後live値ではない。
- TTX未取得の失敗stageは今回ない。`selfVehicle`、`shipTTX`、選択`torpedo` variant、speed/maxDistの各leafはいずれもavailable。`none`は未選択のdeepwater/alternative variantだけである。

## API `ammoParams` との区別

- B15通常162 stateで`torpedoArmament.available=true`、`selectedAmmoStatus=available`、`ammoParamsStatus=available`、`ammoParams`は全state `dict {}`。終了1 stateは軽量形のため`torpedoArmament`自体がない。
- したがって今回の75/9は、`getAmmoParams(selectedAmmoId)`のserializer結果や`ammoParams`の非空化によるものではない。`ammoParams={}`という既存の別経路の制約を、`shipTTX`経由の取得成功で置き換えない。
- 逆に、`ammoParams`が空であることを「APIに性能値が存在しない」ことの証明にもしない。B15で確認したのは、UI descriptor→`shipTTX`の固定variant経路が当該条件で値を返したことだけである。

## 限界・未確認

- 対象はUndineの当該TrainingBattle区間（約17秒、魚雷選択区間は約14秒）だけ。全艦・全魚雷・全戦闘への一般化はしない。
- `ttxStatus=partial`の意味は「固定3 variantの一部だけが存在する」であり、selected leafの欠測ではない。この集約値だけを見て性能取得失敗と判断しない。
- speed/maxDistの数値が補正前の静的TTX候補であること、deltaの表示意味、unitHintの単位確定、live値への変換は未確認。
- 「15b」および「不具合なし」のゲーム内意味は本記録だけでは確認しない。

## 次の最小アクション

- B15の当該条件については、追加の実機試験やreload操作を要求しない。実装・ゲーム・manifestは今回変更していない。
- 最小のコード作業としては、実装変更ではなくoffline回帰を1件追加する案が適切。匿名fixtureで「3 variant中`torpedo`だけavailable、deepwater/altはnone」のとき`ttxStatus=partial`かつ選択`torpedo`の`variantStatus`/`leafStatus`はavailable、pinger選択時はtop=`notApplicable`でrouteのpartialが残る、を固定する。これはテスト専用で、ゲーム側やmanifestへ触れない。
- その後のP1は、B15で未確認の補正後live値・tooltip上書き・残射程/寿命の分離へ進む。`ammoParams`空の原因追跡は、shipTTX経路の成立とは別課題として扱う。
