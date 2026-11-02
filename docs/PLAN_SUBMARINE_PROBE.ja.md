# 潜水艦固定診断の実装・検証計画（0.3.11実装済み）

## 目的と範囲

本書は実装境界・JSON形・取得回数・試験記録。実装は正本の[`submarine_telemetry.py`](../WowsExtractor-torpedoes-client-test/res_mods/PnFMods/WowsExtractor/submarine_telemetry.py)、Main統合は0.3.11。静的調査は [`WowsExtractor-torpedoes-client-test/docs/RESEARCH_SUBMARINE_SYSTEMS.ja.md`](../WowsExtractor-torpedoes-client-test/docs/RESEARCH_SUBMARINE_SYSTEMS.ja.md)（2026-11-01）を参照する。

対象は (1) 自艦Submarine/Battery、(2) `waveHit` collection、(3) 魚雷UI entity上の明示`depth`だけ。GUIの `getFirstWatcher` / `getSingleComponent` / `getSingleEntity` はPython実機の可用性がunsupported/unknownであり、既存Pythonへ持ち込まない。別namespaceのID join、敵艦の新規走査、深度差・区画・ping誘導先の推定、値の履歴／持越しは対象外。

## 根拠と確度

- `C:\Users\kitta\Documents\playground\wows-mods\mino-smoke\research\extracted\gui\data\Components.xml`（ローカル抽出物。正本記載ではbuild 13357625由来、revision/hash未確認）を実読。`Submarine`に`depthIndex`, `depthRanges`, `depthStatesValues`, `showDepth`, `depth`, `depthValues`, `nearestDepthIndex`、`Battery`に後掲の固定候補、`WaveHit`に`targetID`, `lifeTime`, `maxLifeTime`, `alertTime`, `hitCount`, `isActive`, `weaponType`が定義される。スキーマ定義はPython可用性・生値・意味・単位を証明しない。
- `C:\Users\kitta\Documents\playground\wows-mods\mino-smoke\research\extracted\gui\unbound2\pc\battle\submarine_battery.unbound`を実読。UIは`CC.selfVehicle` entityの`.battery`からvalue/rates/stateを参照し、countdown/timerと組み合わせて表示値を作る。
- `C:\Users\kitta\Documents\playground\wows-mods\mino-smoke\research\extracted\gui\unbound2\pc\battle\telegraph.unbound`を実読。depth UIは自艦entityの`.submarine`と同entityの`.battery`を参照する。深度表示には`CC.cruise`の`cruise.value`、`abs`、`depthValues`等の表示ロジックも使うため、これらを同一の生深度値として扱わない。
- `C:\Users\kitta\Documents\playground\wows-mods\mino-smoke\research\extracted\gui\unbound2\pc\battle\weapons_panel\slots\slot_pinger_info.unbound`を実読。UIは`$datahub.getCollection(CC.waveHit)`の件数とTTX `pinger.maxTargets.value`を表示し、selfVehicleは`getFirstWatcher`経由。前者はcollection名の静的手掛かりのみ、後者やGUI getterはPython呼出し根拠にしない。
- `unbound2/pc/battle/markers/wave_hit_marker.unbound`（正本の参照先、今回もgrepで確認）ではlifeTime/hitCount/isActive/alertTimeを表示する。UI式が示すのは表示用途で、Python側の意味・更新時刻基準は未確定。
- Pythonは`Main.py`から`torpedo_telemetry.py`を呼ぶ。B11以降で採用している成功パターンに合わせ、Python側は`getEntityCollections(name) → entity[CC.key]`だけを使い、GUI専用watcher/single getterへ退行しない。既存probeは固定field、最大32行、有限scalar、`fieldStatus`、失敗のfail-closedを採用済み（torpedo専用probeは別上限）。`CC`はMain.pyで`constants.UiComponents`から取得する。

静的資料上の名称を候補に使うだけであり、いずれも実機でPython取得済みとはしない。利用可能性と意味確定を別々に記録する。

## 実装配置・取得回数

実装は独立module `submarine_telemetry.py` に固定診断helperを置き、`Main.py`から両import経路とsafe boundary + callsite `_try` を通して呼ぶ。通常stateにトップレベル`selfSubmarineProbe`と`waveHitProbe`を追加する。`uiTorpedoProbe` rowへのdepth追加は本版では実装範囲外。診断失敗は他のstate採取を落とさない。

1 state snapshot（採取周期案1Hz、stateは現行約10Hz）当たり、追加collection getterは **`selfVehicle`を1回、`waveHit`を1回**。既存の`torpedo` collectionは既存ui torpedo probeの1走査を再利用し、その同じentityで`CC.torpedo.depth`を読む。新probe内で同じcollectionを取り直さない。1Hz外のstateでは直近診断値を持ち越さず、設計実装では毎state呼ぶなら固定頻度制御を明示し、未採取フレームはstatus=`unknown`/reason=`notSampled`とする（前回値は再掲しない）。診断時刻は当該stateの`ts`をsample timestampとして使い、取得成功を表す時刻とし、ゲーム時刻基準そのものは既存`ts`の契約に従う。

### 自艦collectionとcomponent gate

- `getEntityCollections('selfVehicle')`を一度だけ呼び、**列挙完了後**に件数を判定する。0件は正常な空と見なさずself vehicle未確定の`unknown`、1件だけが読取対象、2件以上は曖昧として`unknown`（先頭を選ばない）。列挙中例外は部分entityを捨てて`unknown`。上限は2件の存在確認まででよいが、2件目を見つけたら中止して曖昧扱いできる（この場合`complete=false`を明記）。通常の完全成功は`complete=true`。
- collectionが完全に単一の時だけ、そのentityから`CC.submarine`と`CC.battery`のkey/componentを独立に取得する。両者は**同じentity内**にある場合だけ採用。自艦の数値IDやbattle API自己shipとの結合はしない。
- `CC is None`、key不存在/Noneはそのcomponentの`unsupported`。entity component access例外、component None/欠落は`unknown`（見つからないことを「潜水艦ではない」と解釈しない）。componentが見つからなければそのfieldはnull/status unknownまたはcomponent statusを伝播する。`submarine`の有無から艦種を確定しない。

### WaveHit collection

- `getEntityCollections('waveHit')`を一回だけ呼ぶ。最大32行を固定allowlistで出力する。33件目を観測したら`truncated=true`。正常に空なら`status=available, rows=[]`。iterator中の例外は部分を成功扱いせず`status=unknown, rows=[]`（または明示的`partial`を採用するなら既存probeと同じ規約で部分件数のみ、完全一覧と誤認させない）。推奨は魚雷probe既存規約に合わせて破棄しunknown。
- component keyは`CC.waveHit`。各entityは`entity[CC.waveHit]`から読む。`entity.id`は`entityIdCandidate`として別記できるが、`targetID`とのjoin・主キー扱いはしない。
- `targetID`はComponents.xml commentのWaved vehicle ID候補。vehicle IDと確証なしに`ships[].vehicleId/playerId/uiId`へjoinしない。`hitCount`はraw整数候補で、一重/二重の正規化をしない。複数WaveHit行が同じtargetIDを持つ場合も統合しない。

## 固定出力契約案

以下はJSON形の設計例（値は架空）。この追加分は診断でありsemanticsは常に`unverified`。

```json
{
  "selfSubmarineProbe": {
    "source": "dataHub.selfVehicle",
    "status": "available",
    "semantics": "unverified",
    "sampleTs": 12.3,
    "collection": {"status":"available","complete":true,"count":1},
    "entityIdCandidate": null,
    "components": {
      "submarine": {"source":"dataHub.selfVehicle.submarine","status":"available","fields":{},"fieldStatus":{}},
      "battery": {"source":"dataHub.selfVehicle.battery","status":"available","fields":{},"fieldStatus":{}}
    }
  },
  "waveHitProbe": {
    "source": "dataHub.waveHit",
    "status": "available",
    "semantics": "unverified",
    "sampleTs": 12.3,
    "rows": [], "truncated": false, "partial": false
  },
  "uiTorpedoProbe": {
    "rows": [{"depthSource":"dataHub.torpedo.depth","depthStatus":"available","depth":20.0,"depthRawType":"float"}]
  }
}
```

各componentの`fields`には全fieldを固定キーで含め、欠測値は`null`、同じ名前の`fieldStatus`で状態を表す。waveHit rowも`fields`/`fieldStatus`の形を使い、`entityIdCandidate`、`componentStatus`を別に置く。値の読み取り状態だけでなく型検証後の状態を反映する。

| source component | 固定field allowlist | validation |
|---|---|---|
| `CC.submarine` | `depth`, `depthIndex`, `showDepth`, `nearestDepthIndex` | `depth`は有限numberかつbool除外。index類も有限number（整数性は整数型のみ要求せずrawを保つ）、`showDepth`は`type(value) is bool`のみavailable。`depthRanges`, `depthStatesValues`, `depthValues`はcontainer/深さ・サイズ制約が増えるため初版では読まない。 |
| `CC.battery` | `value`, `burnedValue`, `maxCapacity`, `baseSpendRate`, `baseRegenRate`, `currentRate`, `burnRate`, `batteryState`, `isPotentiallyBurning` | 数値はfinite（bool除外）、`isPotentiallyBurning`は厳密bool。stateはfinite number rawのままで列挙名に変換しない。 |
| `CC.waveHit` | `targetID`, `lifeTime`, `maxLifeTime`, `alertTime`, `hitCount`, `isActive`, `weaponType` | ID/state/countはfinite number raw（bool除外）、時間もfinite number raw、`isActive`は厳密bool。 |
| existing `CC.torpedo` | `depth`のみ | 同じtorpedo entity内の有限numberのみ。`uiId`との照合・魚雷API行への追加joinなし。 |

`depth`（Submarine componentとTorpedo component）は**直接componentから読んだ生候補**であるが、物理的な正負、単位、基準面、API positionとの関係は未確定。`depthIndex`/`nearestDepthIndex`/`batteryState`/`weaponType`は列挙値候補の生値。`value`, rates, lifeTime類もcomponentの生読み取り値であり単位や残時間解釈は未確定。`showDepth`/`isActive`/`isPotentiallyBurning`は型の通ったraw boolであって意味未確定。

派生値は出さない。特に`depthDifference`, `batteryPercent`, `batteryTimeRemaining`, rateのabs/符号反転・合算、WaveHitの残存時間、targetごとの統合・ping hit回数の補正、UIの表示値再現、魚雷座標yからのdepth代用は禁止。`telegraph`の`cruise.value`絶対値や選択深度もこの診断の生Submarine.depthへ混ぜない。

## Helper再利用・status規則

`torpedo_telemetry.py`既存の`_probe_component_key`, `_probe_component`, `_probe_read`, `_finite`, `_candidate_value`, `_probe_fields`を再利用する。`_probe_fields`だけではbool/finite validationを十分に表現しないため、fieldごとにvalidatorを追加し、入力の真偽値を数値として通さない。任意`dir()`/`repr()`/method呼出しは行わない。固定フィールドの読取失敗を`fieldStatus`に残し、raw typeは必要な候補fieldにだけ限定型名（bool/int/float/string/NoneType/object）を付ける。unknown objectは値をserializeしない。

status規約（各レベル独立）：

- getter自体がない、またはCC keyが存在しない/None: `unsupported`。
- getter例外、getter戻り値None、collection/component access例外、component欠落、field欠落/None、非有限値、bool/数値型不一致: `unknown`。field欠落等の詳細は`fieldStatus`と`reason`（`attributeMissing`, `attributeReadException`, `noneValue`, `nonFiniteNumber`, `expectedBoolean`, `expectedFiniteNumber`, `componentMissing`, `componentReadException`）に分ける。
- collection getter成功しiteratorを最後まで列挙: `available`。空collectionもavailableであり、count=0を「対象なし」の観測としてのみ扱う。selfVehicleだけは0件を唯一の自艦として採用せず、self-level unknown。
- waveHit 32件上限を超えたら`truncated=true`。列挙完了した範囲はavailableだが、完全集合ではない。途中例外で一部結果を残す場合は`partial=true,status=partial`に限り、実装簡素化優先なら部分行を破棄しunknown。混在させずテスト固定。
- component全体status=`available`はcomponentを読めた意味だけ。すべてのfieldがavailableとは限らない。top-level statusは下位statusの要約であり、個別statusを潰さない。
- false/0はその型・有限性が正しければ保持。欠測や型違いをfalse/0へ置換しない。無限/NaNはJSONへ出さずnull。

取得値は一回の診断sample内だけのsnapshot。前回値、lastSeen、履歴、TTL、同期補完は持たない。取得できないときは現在値をunknownにし、直近値を転記しない。

## 固定回帰テスト（実装済みDone条件）

`tests/test_torpedo_telemetry.py`に固定診断helperのテストを追加し、`tests/test_visibility_observations.py`同様に出力を`json.dumps(..., allow_nan=False)`できることも確認する。実機取得根拠とは分離する。

1. `CC.selfVehicle` entity単一・完了時だけ同entityからsubmarine/batteryを読む。双方存在、片方のみ、key欠落、CC None、entity indexing例外を独立検証。複数entity時に先頭選択しない。空/None/collection getter欠落/例外/iteration中例外を区別し、部分列挙を単一complete扱いしない。
2. `getEntityCollections`呼出し回数をspyで固定: selfVehicle 1回、waveHit 1回、既存torpedo probe 1回。診断depth付与によるtorpedo collection再取得なし。unsupported時も例外をMain state側へ漏らさない。
3. waveHit zero/1/32/33 entity、欠component、component keyなし、iterator例外、行ごとの各field欠測を検証。32行上限、`truncated`、partial/unknown規則、空成功の区別、targetID join/統合をしないことを検証。
4. `depth`は0と負数と正数をraw保持するがyからは作らない。torpedo depthは同一entityの`CC.torpedo`のみ、別entity depthやAPI uiId一致で補完しない。`position.y=0`/非zero/Noneのいずれでもdepth候補に使わない。
5. 数値のfalse/true、NaN、±Inf、文字列、None、descriptor objectを各fieldへ入力。boolはnumeric gateを通らず、有限値だけavailable、strict booleanはboolのみavailable。`hitCount=0`, `isActive=false`, `showDepth=false`を有効な生値として保つ。
6. 2 sampleの間に値を削除/例外に変えた場合、2回目で前回値を再掲しない。標本化外ならnotSampled/unknown、履歴を保持しない。
7. status/source/schema形、component/field別status、全部の固定キー、上限、非有限のJSON安全性をassert。既存魚雷/weapon probeやstate fieldsを変更しない回帰を含める。

## 最小Undine実機試験案（次の実機作業）

実装・レビュー・別環境導入後に、現在の試験中環境を上書きせず通常の記録手順で1回の訓練戦を行う。ゲームbuild、mod版、ATM有無、艦、時刻、画面上の値を記録し、ログ共有は匿名化する。

1. 記録開始後、浮上・潜望鏡・最大深度を可能な範囲で短く保持し浮上回復する。各状態の`selfSubmarineProbe`生値/statusと画面深度/Batteryを時系列記録。負担ならこのBattery/depth段階だけでよい。
2. 任意の別フェーズで停止bot一隻へのpingを1回、続けて2回試す。`waveHitProbe.rows`の固定raw fieldsとUIをそのまま比較する。ターゲットjoinは行わず、操作との対応を観測事実としてだけ記録。
3. 可能なら音響魚雷を発射し、既存torpedo UI entityのdepth候補とAPI torpedo position、UI誘導表示を別々に記録。namespaceが確定しないID同士を結びつけず、誘導先・命中・消滅理由を結論しない。
4. 診断status、missing/unknown/unsupported、sample間隔・truncated、fps/記録サイズを確認する。`available`は取得成功であって単位・意味の確定ではない。UIとの対応が取れない値や操作不成立はunknown/未実施とする。成功を装うための値補完をしない。

## 実装・試験時の禁止事項

- `getFirstWatcher`, `getSingleComponent`, `getSingleEntity`をPythonから呼ばない。
- `selfVehicle`単一complete以外からself値を採らない。GUI collection/watcher式やTTX値をPython契約にしない。
- WaveHit targetIDをship IDsとjoinしない。component idをtargetIDと同一視しない。
- `position.y`, Main.pyの地表用`y=0` fallback、マップ位置・深度段階・UI cruise値から深度を合成しない。
- schema固定allowlist外を列挙・再帰コピーしない。component/UIへ書き込まない。
- collection取得失敗を空成功に変えない。過去値の保持、長時間履歴、推定残秒・割合・hitCount解釈を追加しない。

現状の実機観測結果はこの計画の設計根拠・offline testsと混同せず、別途validation記録へ追記する。B18 selectorについてはraw実機記録とoffline exact composite-key選択確認を分けて記録済みであり、0.3.10修正版の実機再試験は要求しない。
