# 0.3.6 実機記録 B11：context／clock route 検証

対象は正本 `recordings/without-atm-b11.jsonl`。ユーザー実機報告は「b11。9:40。不具合なしで終了」。試験意図はMinotaur訓練戦で収集開始後約20秒に魚雷を選択し、約10秒後に退出。以下はJSONLの観測と実装schemaを分けて記す。JSONLはPython標準`json`で1行ずつ逐次解析し、ファイル全体を読み込んでいない。個人名・実IDは記載しない。

## 記録・schema

| 項目 | 観測 |
| --- | --- |
| ファイル | `recordings/without-atm-b11.jsonl`、6,104,965 bytes、356行、JSON parse error 0 |
| 行内訳 | meta 2行、state 354行 |
| 版 | meta両方でmod `0.3.6-python-hub-diagnostics`、schema 1、apiVersion `1.0` |
| envelope観測時刻 | 全体 2026-11-01 03:05:42.870945–03:06:58.228786 UTC。active中 03:06:21.368077–03:06:58.068345 UTC |
| state `active` | true 352、false 2。activeの`ts`範囲 180.003200–216.695496。終端falseは`ts=216.787749` |
| 記録の連続性 | active区間は約36.70秒。初期false state (`ts=134.525531`) とactive開始の間に約45.48秒の`ts`差がある。連続した9分40秒の記録ではない |

Main.pyの`_build_state()`はactive frameで各probeを出力する。一方、`_on_battle_quit()`が書く終端inactive stateは簡略schemaでprobe自体を含まない。この終端欠落はprobe失敗ではない。解析対象の352 active stateでは`weaponContextProbe`、`gameClockProbe`、`weaponHubProbe`が各1回ずつ存在し、probe例外を示す`error`もない。

`torpedo_telemetry.py`の候補はUI由来で、ゲーム全条件の意味は未検証。Main.pyはsafe probe結果を独立fieldとして保存する。`available`は候補値の読取成功を表す。今回のユーザー報告（「9:40。不具合なしで終了」）はJSONLとは独立した画面・操作観測として扱う。raw候補の時系列とこの報告を合わせると、今回の試験条件では選択と数値・操作が整合したことを確認できる。ただし画面の撮影記録や同期点を含む独立計測ではなく、全条件・単位意味の保証、または確定サーバー情報とはしない。

## weaponContextProbe：段階別結果

全352 active stateで結果は安定。全体statusは`available`。以下のstatus数は各352回（field単位は最大704回）である。

| route／段階 | status／raw形 | 判定 |
| --- | --- | --- |
| `getFirstWatcher(CC.selfVehicle)` | getter `unsupported`、key `available`、call `unsupported`、entity `unknown`。singleton selfVehicle status `unsupported` | このrouteはgetter段階で止まり、entity／controllerへ到達しない。component key欠落ではない |
| `selfVehicle` collection | getter/call/key/componentすべて`available`。1 row/frame | `selectedWeapon`: field `available`、raw int `0` 全352回。`activeIdWeapon`: field `unknown`、raw/type null 全352回 |
| `weaponController` collection | getter/call/key/componentすべて`available`。1 row/frame | `selectedWeapon`: int raw `0`が202回、`2`が150回。`activeIdWeapon`: string raw `"torpedo"`が352回 |
| `selfVehicle.weaponController` singleton経由 | top-level `weaponController.status=unknown` | 前段のselfVehicle watcherで止まるため、このpath上ではcontrollerを読んでいない。collection routeの結果とは別 |
| `slotContext` | `unavailable`が352回 | 固定の未取得route。UI SlotRenderer `_id`／特定slotとの対応付けは実施していない |

ここでの`unknown`を「属性なし」「値None」「属性getter例外」のどれかに特定できない。`_probe_read()`がこれらを同じstatusへ畳み込むためであり、当該collection fieldのraw/typeもnull。実装上、component自体は`available`で、component欠落ではない。一方、`unsupported`はselfVehicle singleton getterが非対応と明示された段階であり、key欠落・例外とは異なる。collection routeは別に成功している。

### 時系列

- active開始`ts=180.003200`時点の`weaponController.selectedWeapon`候補は0。
- 最初にraw 2へ変わるstateは`ts=201.338543`、active開始から**21.335秒後**。以降のactive stateでは2（合計150/352 state）。これはユーザーの「約20秒後に魚雷選択」と時間的に近い候補変化だが、fieldのenum意味はこのログ単独では検証されていない。
- `weaponController.activeIdWeapon`候補は全区間`"torpedo"`。選択候補のraw変化は`selectedWeapon`側で観測された。
- 最終active stateは`ts=216.695496`。raw 2への変化から最終active stateまでは**15.357秒**、inactive終端stateまでは**15.449秒**。申告意図の「約10秒後退出」と同じ長さではない。ログ境界上の観測として記し、異常終了や操作失敗とは判定しない。

## gameClockProbe：全候補route

全352 active stateでprobe全体statusは`available`だが、これは主にcollection候補が読めたため。singleton clock routeはavailableではない。以下の各routeは全352回同じstage status。

| 候補route | key | getter | call | component | field/status・raw |
| --- | --- | --- | --- | --- | --- |
| `timer.currentTime` via `getSingleComponent` | available | unsupported | unsupported | unknown／未到達 | 候補status unsupported、raw/type null |
| `timer.currentServerTime` via `getSingleComponent` | available | unsupported | unsupported | unknown／未到達 | 候補status unsupported、raw/type null |
| `battleInfo.duration` via `getSingleComponent` | available | unsupported | unsupported | unknown／未到達 | 候補status unsupported、raw/type null |
| `battleTimer.battleTime` via `getSingleEntity(CC.battleTimer)` | available | available | unknown | unknown | fieldまで到達せず、候補status unknown、raw/type null |
| `battleInfo.duration` via `battleTimer` entity内 | available | available | unknown | unknown | fieldまで到達せず、候補status unknown、raw/type null |
| named collection `timer` | key available | getter/call/component available | available | available | `currentTime` float available 352/352、`currentServerTime` float available 352/352 |
| named collection `battleTimer` | key available | getter/call/component available | available | available | `battleTime` int available 352/352 |
| named collection `battleInfo` | key available | getter/call/component available | available | available | `duration` float available 352/352 |
| `battleTimeLeft` | 該当なし | 該当なし | 該当なし | 該当なし | unknown 352/352、raw null、inferred true。singleton両rawがないため計算されていない |

collectionの実測raw推移（B11は`selfVehicle`、`weaponController`、`timer`、`battleTimer`、`battleInfo`が各1 row/frame。単一row観測はこのnamed collection・試験区間に限る。意味・単位は未検証）：

- `timer.currentTime`: 179.994551 → 216.695496（float）。Main stateの`ts`とほぼ同時に同じ数列で進む。
- `timer.currentServerTime`: 約1793502380.911 → 1793502417.612（floatのepoch様値）。UTC envelope時刻とは概ね同じ区間で進むが、ユーザーが報告した「9:40」の時計だとは確認できない。
- `battleTimer.battleTime`: 0 → 37（int、0から約1秒ごとに増加）。
- `battleInfo.duration`: 10.0（float）で全active区間一定。

実装`game_clock_probe()`の`battleTimeLeft`式は同一`getSingleEntity(CC.battleTimer)`から取得したdurationとbattleTimeの両方がavailableの場合だけ候補化する。今回collection routeのraw値をsingleton routeへ代入・合成していないのは正しい。実装上、`getSingleEntity`のcall `unknown`は例外とNoneを区別しない。後続component/fieldのunknownも欠落・None・読取例外の内訳を出さない。対してcollectionのgetter/call/component/fieldはすべてavailableで、欠落や例外が起きた観測ではない。

### 「9:40」との対応

JSONLでは`weaponController.selectedWeapon`がactive開始+21.335秒に0→2へ変化し、同じactive区間の`battleTime`は0→37、`duration`は10で一定だった。独立したユーザー画面報告は9:40で、魚雷選択と表示数値・操作は整合したとの報告である。durationを分、battleTimeを秒とするUI式`duration * 60 - battleTime`なら約9:40となり、今回の報告・候補値と整合する。これは**当試験条件での限定的な対応確認**であり、collection間は別entityなので同一entityとは扱わず、同一snapshot timestampの別route値とscope assumptionに基づく推定である。全条件の単位・意味、確定サーバー残時間としては保証しない。`timer.currentTime`やepoch様`currentServerTime`を残り時間へ読み替えない。

## 既存 weaponHubProbe／slotの別観測

全352 active stateでoverallと3 collection routeが`available`。key、collection getter/call、各row component取得はいずれもavailableで、partial/truncatedなし。

| collection | row数／frame | field status |
| --- | ---: | --- |
| `weaponSlot` | 3 | `id/type/state/active/selected/shotCount/ammoParamsId/ident`すべてavailable。別component `progress.value/max`もavailable |
| `ammo` | 3 | `id/hasSecondaryAmmo/isAutoUsage/squadId`および`viewData` routeはavailable |
| `serialLoad` | 2 | `index/weaponType/state`および別progress `value/max`はavailable |

weaponSlotの`ident="torpedo"`候補rowでcomponent field `selected`は全352 state false、`state`候補は1から3へ変化し以後3。`progress`は別componentで取得成功。別の`weaponController.selectedWeapon`候補は0から2へ変化した。この違いは**異なるrouteの観測値**であり、`selected=false`を「魚雷を選んでいない」と解釈しない。probeはUI SlotRenderer `_id`とcollection rowを結合せず、status成功もUI意味の確認ではない。serialLoad/ammoとslot/contextの間もjoinしない。ID値は本報告に転記しない。

## 結論・次の静的調査

1. 取得全滅ではない。context collectionのcontroller候補とclockの3 named collectionで実値が継続取得されている。singletonだけの失敗とcollectionの成功を混同しない。
2. controller raw `selectedWeapon`の0→2は操作申告から約21.335秒後で、ユーザー画面報告と操作順に整合する。これは当試験条件の選択確認であり、enum意味・他条件への一般化は未保証。slot `selected=false`は別観測であり、選択を否定しない。
3. 退出間隔のJSONL境界は選択候補変化から約15.4秒。これは約10秒というAI目安との差であり、ユーザー不具合ではない。実機報告「不具合なし」を維持し、問題化しない。
4. 同じ試験を再要求しない。B09/B10の装填候補不整合は、0.3.7の時計観測を使う次の1回で確認する。過去ログへ遡って時計式や意味を当てはめない。

この文書はB11時点の観測記録であり、後続0.3.7の追加観測仕様を記述するものではない。0.3.3 ZIP・manifest・ゲーム導入は変更していない。
