# 選択魚雷の種類・速度・最大射程：取得経路調査

## 結論

- B12/B14の既存記録では、`torpedoArmament`の選択弾ID取得と`getAmmoParams()`呼び出しは成功statusだが、active中の`ammoParams`は全て空dict `{}`。魚雷性能値が取れた記録ではない。
- 同じ記録の`weaponHubProbe.collections.ammo[].viewData.paramsDescriptor`には`torpedo`と`pinger`があり、slot/controllerの選択候補と合わせると、選択武器からammo viewDataをたどるUI経路は利用可能な固定whitelist診断にできる。これは`getAmmoParams`の選択弾IDとは別のID系統であり、両者を直接joinしない。
- 速度・最大射程のGUI参照先は、selfVehicle componentの`shipTTX.torpedoes`内の魚雷TTX候補である（Python候補経路：`getEntityCollections('selfVehicle') → entity[CC.selfVehicle] → component.shipTTX`）。`TorpedoTTX.speed`と`TorpedoTTX.maxDist`が定義され、TTX UIはそれぞれknots/km表示としている。これは静的艦諸元／TTX表示経路の確認であり、Pythonからの実取得・値の単位・現在弾薬に対する補正後値を保証しない。
- 既存B12/B14ログでselection/viewDataのroute候補は検査できる。`shipTTX.speed/maxDist`自体は当時の出力whitelistにないため、値が取得可能かは未確認。追加の選択・reload実機試験を求める根拠はない。診断実装後に通常の確認記録を読むまでは取得済みにしない。

## 1. B12/B14記録の逐次解析

対象は`recordings/without-atm-b12.jsonl`と`recordings/without-atm-b14.jsonl`。各JSONL行を逐次parseし、各stateの`data`だけを読み、個人名・battle/player/entity/ammo実IDは記録・転記していない。inactive終了stateは通常active観測と分けた。

| 記録 | `torpedoArmament` active通常state | `selectedAmmoStatus` / `ammoParamsStatus` | `ammoParams` |
|---|---:|---|---|
| B12 | 1,643 | 全1,643行でavailable / available | 全1,643行がdict `{}` |
| B14 | 1,472 | 全1,472行でavailable / available | 全1,472行がdict `{}` |

B14の残る1 stateは終了時の軽量stateで、両statusと`ammoParams`は省略/null。これはactive中の空dictとは数えない。結果は「選択IDとAPI呼び出しが成功し、serializerが空dictを返した」までであって、APIの内部SafeClassに速度や射程が存在しないことの証明ではない。

既存の`public_data()`はSafeClass相当の任意objectに対して`dir()`し、public名を`getattr`で読み、method/private名を除く。属性読取失敗も`_get`のdefaultへ畳まれるため、空結果だけでは「`dir()`が空」「全属性が非公開」「属性getter不可／例外」「そのAPI返り値に該当値がない」を区別できない。B12/B14はその差を記録していない。回帰テストの`torpedoSpeed` fixtureはコピー変換を試す擬似objectであり、実ゲームのSafeClass shapeの証拠ではない。

## 2. 既存weapon probeが示す候補route

B12の1,643 active state、B14の1,472 active stateでは、既存weaponHub probeのammo collectionはそれぞれ毎state 2 rows、正常完了。`viewData`の限定field一式も取得され、`paramsDescriptor`は文字列で、観測値の種類は`pinger`と`torpedo`。個々の実ID・ammo名はこのDocに含めない。

記録内の固定値一致を件数だけで検査した結果：

- `weaponContextProbe.observations.controllerSelectedWeapon`のraw値と`weaponSlot.fields.type`は、各active stateで2 slotのうち1つと一致（B12/B14とも全stateで取得）。UI定義には`controller.selectedWeapon == weaponType`というactive判定がある。
- `weaponSlot.fields.id`とammo componentの`fields.id`は各slot/ammo間の完全比較で1対1のexact scalar一致となり、同じammoの`viewData.paramsDescriptor`を取得できた。選択controller/type一致slotからこの一致をたどったdescriptorはB12/B14のログ範囲で`torpedo`または`pinger`と遷移した。
- `weaponSlot.fields.selected`は両記録でtrueにならず、controller selected/typeの代用にはならない。UI定義でも別predicateとしている。
- `selectedAmmoId`は整数、ammo component `id`／`viewData.ammoId`は文字列で、各active stateで直接等値一致しなかった。API IDとviewData IDは異なる表現・経路であり、変換表がないので推測joinしない。
- probeの`ammo.entityIdCandidate`と`weaponSlot.fields.id`は記録で一致しなかった。固定joinを新設する場合はUI sourceが使う`getPrimaryEntity(CC.ammo, slot.weaponSlot.id)`の意味に沿うIDを実装時に確認し、entity row順やtype順でjoinしない。現行記録から根拠のないentity-ID joinを足さない。

上記は既存recording内raw値の整合とUI参照の限定照合。Python/dataHubの正式公開契約や全艦・全弾種の選択意味確定ではない。診断は`source`・段階別status・`semantics=unverified`を保つ。

## 3. 外部GUI定義の実読（抽出物は読み取りのみ）

参照root：`../mino-smoke/research/extracted/gui`。抽出物の由来・build・再ハッシュは今回独立に検証していない。以下はそのファイル内の静的参照であり、Python API契約ではない。

1. `unbound2/pc/battle/weapons_panel/slots/slot_renderer.unbound`：`CC.selfVehicle` watcherのentityと`weaponSlot`を参照し、controllerの`selectedWeapon == weaponType`でslotのactive候補を定義。さらに`slot.weaponSlot.id`をkeyとして`getPrimaryEntity(CC.ammo, ...)`を呼び、そのammo entityの`ammo.viewData`をtooltipへ渡す（おおむね1–24行、285–296行）。
2. `unbound2/pc/battle/weapons_panel/tooltips/weapon_slot_tooltip.unbound`：viewDataの`paramsDescriptor`を読み、`BattleAmmoParameters`に渡す（4–15行、37行）。
3. `unbound2/pc/ttx/ammos/ammo_tooltip_adapter.unbound`：`torpedo`、`torpedo_deepwater`、`torpedo_alternative` descriptorを対応rendererに引き、ForBattleの場合`selfVehicle.selfVehicle.shipTTX`を使う（2–12行、36–52行）。従ってdescriptorは表示テンプレート選択子であり、速度/射程数値そのものではない。
4. `unbound2/pc/ttx/ammos/ammo_torpedoes_tooltip.unbound`：各ForBattle rendererは`_shipTTX.torpedoes.torpedo`、`.torpedoDeepwater`、`.torpedoAlt`のTTX variantを参照（104行以降）。ForDock側も同系統のTTXを使う（31行以降）。battle tooltipの見た目が選択弾variantを選ぶが、GUI定義だけではTTX値が補正前/後か、Pythonで同じobjectに到達できるかは分からない。
5. `data/structs/ttx.xml` 151–161行：`TorpedoTTX`に`maxDist: FloatDiff`、`speed: FloatDiff`がある。`data/structs/common.xml` 130–133行では`FloatDiff`は`value:Number`と`delta:Number`の組。`unbound2/pc/ttx/ship_params/torpedoes_ttx.unbound` 68–103行では`torpedoTTX.maxDist`を`VALUE_CONFIG.KILOMETER`、`torpedoTTX.speed`を`VALUE_CONFIG.KNOT`として表示する。UIの単位表示根拠はあるが、Pythonでのshape・deltaの表示意味・dataHub raw値のunit変換は未確認。
6. 同`ship_params/torpedoes_ttx.unbound`は通常・deepwater・alternativeの複数TTX variantを別々に表示する。`shipTTX`値は艦のTTX諸元候補であり、選択slot descriptorによるvariant選択は静的UI上確認できる。Battle tooltipではalternative parameter等の表示上書きがあり得るため、実装は`speed`を`staticTTXDisplayCandidate`/`liveAdjusted=false`/`battleTooltipAlternativeOverridePossible=true`のmetadata付き候補として出し、代替値を合成しない。現在選択したammoのIDに関する実測join、艦長スキル等の補正反映、他艦でのshapeは未確認。

## 4. 固定revisionの公開API資料

参照revisionは`wgmods/Mods-API-Documentation` commit [`01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2`](https://github.com/wgmods/Mods-API-Documentation/tree/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2)。

- [`battle.md#getAmmoParams`](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/battle.md)：`getAmmoParams(ammoID)`は「shell」の情報objectとして説明され、魚雷性能field一覧やSafeClass属性は記載しない。
- [`battle.md#getSelectedAmmoId`](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/battle.md)：現在の選択ammo IDを返すintとして記載。魚雷での`getAmmoParams`対応やTTXとのID結合を保証しない。
- このrevisionの`docs/PythonAPI/Classes`に一般Ammo/SafeClassの公開field一覧はない（`AmmoModifiers`等は別object）。従って未文書化の`torpedoSpeed`等をpublic API保証として追加しない。

## 5. 実装可能な最小whitelist診断案

選択性能を確定出力にせず、現行の`weaponHubProbe`/`weaponContextProbe`へ局所的な診断を加える案。probe失敗は局所化し、通常stateや既存取得値に影響させない。

### Routeとフィールド

1. **旧案を訂正**：`getFirstWatcher(CC.selfVehicle)`はB11でPython API unsupportedを確認した失敗経路であり、再利用しない。成功根拠は`getEntityCollections('selfVehicle')`の単一row → `entity[CC.selfVehicle]` → componentの`shipTTX`。このcomponent階層を厳密に読み、`shipTTX`属性をentity等へ総当たりしない。元のentityは通常whitelistに保存されないため、完全な既存collection結果を再利用したうえで、固定名`selfVehicle`を一度だけ再取得する。単一rowかつcompleteのみ許可し、複数・partial・truncatedはunknown。
2. 既存`controllerSelectedWeapon`単一row候補とweaponSlot collectionの各rowについて、UI参照に沿った**raw exact scalar equality**で`controllerSelectedWeapon == slot.weaponSlot.type`候補を記録する。0/複数match、collection partial/truncated、field欠測はselected候補unknownとし、row順・型名の推測joinをしない。実装では`fields.type`をraw scalarとして読み、`fieldStatus.type`がavailableの場合だけ比較する。type/id/component欠測rowを無視して残り1 rowを一意matchにしない。
3. 一意selected slot候補の`weaponSlot.id`とammo componentの固定field `ammo.id` をexact一致照合し、そのrowの`viewData.paramsDescriptor`だけをvariant selector候補にする。現行記録でslot idとammo component idは一致するが、API契約/意味は未検証としてmatch statusを出す。`selectedAmmoId`、`ammoParamsId`、viewData.ammoIdはこのrouteにjoinしない。`fields`はraw scalar、`fieldStatus`は別、`fieldMeta.stringLength/truncated`は元文字列長のmetadataである。空/空白のみ/128文字超過で切り詰められたID、bool、型の異なる数値（Python2 int/longの偽陰性を含む）はjoinしない。0は有効値として保持し、前後空白や大文字小文字の正規化はしない。
4. descriptorが`torpedo`なら`shipTTX.torpedoes.torpedo`、`torpedo_deepwater`なら`torpedoDeepwater`、`torpedo_alternative`なら`torpedoAlt`だけを選択variant候補にする。descriptor未知/欠測、selected slot不一意、dataHub field不在なら別variantへfallbackせずunknown。
5. `shipTTX.torpedoes`の通常/deepwater/alternative各variantから固定候補を最大3つ採取し、選択descriptor候補はそのうち対応する一つだけを参照する。`speed.value/delta`と`maxDist.value/delta`だけを読む（`FloatDiff`自体をscalar化しない）。未知selectorでもraw固定variant候補は調査用に出すが、選択値へのfallback合成は禁止する。これはTTX表示sourceの**静的諸元候補**であり、補正後ライブ値とは断定しない。外部UI根拠だけでdeltaを加算しない。`torpedoArmament.selectedAmmoId`自体は既存出力を維持し、join済みとは表現しない。

### 出力/status/bounds

たとえば`selectedTorpedoParamsProbe`に次の固定形を持たせる：

```json
{
  "source": "dataHub.getEntityCollections('selfVehicle')[CC.selfVehicle].shipTTX.torpedoes[variant]",
  "status": "unknown",
  "semantics": "unverified",
  "selection": {"source": "weaponController+weaponSlot+ammo.viewData", "status": "unknown", "descriptor": null},
  "variant": null,
  "variantStatus": "unknown",
  "leafStatus": "unknown",
  "ttxStatus": "unknown",
  "stages": {"selection": "unknown", "selfVehicle": "unknown", "shipTTX": "unknown",
             "variants": "unknown", "variant": "unknown", "leaf": "unknown"},
  "displaySemantics": {
    "speed": {"candidate": "staticTTXDisplayCandidate", "liveAdjusted": false,
              "battleTooltipAlternativeOverridePossible": true},
    "maxDist": {"candidate": "staticTTXDisplayCandidate", "liveAdjusted": false}
  },
  "fields": {
    "speed": {"source": "...speed.value", "status": "unknown", "raw": null, "type": null, "unitHint": "knots (TTX UI)", "semantics": "unverified", "delta": {"source": "...speed.delta", "status": "unknown", "raw": null}},
    "maxDist": {"source": "...maxDist.value", "status": "unknown", "raw": null, "type": null, "unitHint": "km (TTX UI)", "semantics": "unverified", "delta": {"source": "...maxDist.delta", "status": "unknown", "raw": null}}
  }
}
```

- Field単位statusは`available`（bool以外の有限数値のみ）、`missing`、`none`、`readError`、`nonNumeric`、`nonFinite`、`outOfBounds`等を分ける。親経路は`unsupported/unknown/partial/truncated`を既存probe慣例に合わせて段階別に記録し、未知を0へ置換しない。`value`と`delta`は独立に読み、片方の失敗を他方へ流用しない。
- top-level `status`は選択されたvariantの結果だけを表す。selfVehicle collectionがavailableというだけではavailableにしない。selection unknownならtopもunknown、pingerはtop `notApplicable`とし、TTX routeの失敗は`ttxStatus`/`stages`へ別途残す。`variantStatus=available`（親variant取得）は`leafStatus=available`（speed/maxDist value/delta）を意味しない。
- descriptorは型検証済みstringまたはnullだけを出す。未知stringはそのまま記録してfallbackせず、非string/None/128文字超過/field欠測はdescriptor nullでunknownとする。前後空白・大文字小文字の正規化はしない。
- 防御的な数値上限は`speed.value/delta`と`maxDist.value/delta`それぞれ有限数値かつ`-1,000,000 <= raw <= 1,000,000`の範囲だけ出力し、範囲外は`outOfBounds`でraw=nullとする。deltaは負値もあり得るため符号を保持する。これはJSON/diagnostic保護の広いhard capで、ゲーム内妥当性・unit検証ではない。valueが0の場合も意味確定まではrawとして保持する。
- descriptor文字列128文字、field/status固定whitelist、TTX variant最大3、選択slot候補最大32、ammo候補最大32、container depth最大3・合計64要素まで。複数rowや列挙例外は`partial/truncated`で識別。API呼出し・UI操作・ファイル書き込みはしない。
- unitHintは抽出UI表示に由来するラベルであり、出力の`unit`確定値ではない。実装後にfield shape、値の取得可否、variant追従を確認してから契約へ移す。

この案なら既存recordingでselection/descriptor経路のoffline回帰を作れる。`shipTTX`数値は現行ログに保存されていないため、コード追加後の一度の通常診断記録で取得statusを確認する必要があるが、追加のreload操作や再試験手順は不要。速度・最大射程の実値がunknownならunknownのままにする。

## 6. 区別すべきデータ

| 値 | 性質 | 今回の扱い |
|---|---|---|
| `torpedoArmament.selectedAmmoId` | 公開API選択ammo ID | B12/B14で取得済み。viewData IDやTTX variantと等値joinしない |
| `torpedoArmament.ammoParams` | `getAmmoParams(selectedAmmoId)`のserializer結果 | B12/B14ともactive全行 `{}`。API performance fieldsは未取得 |
| `ammo.viewData.paramsDescriptor` | UI ammo entityの描画descriptor | B12/B14で`torpedo`/`pinger`を取得。TTX variant表示選択子候補 |
| `selfVehicle.shipTTX.torpedoes.*` | Battle tooltip/ship TTX rendererが参照する諸元候補 | `speed/maxDist`が`FloatDiff(value,delta)`の静的shapeと表示単位ヒントを確認。Python取得・補正後ライブ対応は未確認 |
| `torpedoes[].motion.horizontalSpeed` | 位置差分による観測運動 | game world units/sの派生候補。魚雷性能速度の代用禁止 |
| 観測累積距離／時間 | telemetry開始後の`observedDistance/Age` | 残射程／残存寿命ではない |

飛翔中の残射程・残寿命は今回の調査対象外であり、上記TTX最大射程、motion速度、観測累積値から推定して代用しない。

## 参照

- `docs/OUTPUT_SPEC.ja.md`「`torpedoArmament`」「`weaponHubProbe`」
- `docs/P1_CODE_RESEARCH.ja.md`「3. 装填・魚雷性能」
- `docs/VALIDATION_0.3.7_B12_WEAPONS.ja.md`：B12 collection取得範囲と別経路の注意
- `docs/VALIDATION_0.3.8_B14_RELOAD.ja.md`：B14の次段階調査方針
- `res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py`：`public_data`, `weapon_hub_probe`, `weapon_context_probe`, `armament`
- `tests/test_torpedo_telemetry.py`：ammo SafeClass相当serializerとfixed viewData whitelistのfixture test
