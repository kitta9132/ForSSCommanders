# 魚雷の残射程・残存寿命とtooltip補正値：限定静的調査

## 結論

- 0.3.9 B15ではUndineの選択descriptorが`torpedo`の区間で、選択TTX候補`speed.value=75.0`、`speed.delta=0`、`maxDist.value=9.0`、`maxDist.delta=0`を取得し、ユーザー報告の画面表示75kts/9kmと数値上一致した（[VALIDATION_0.3.9_B15_TTX.ja.md](VALIDATION_0.3.9_B15_TTX.ja.md)）。ただし、これは船のTTX候補であり飛翔中魚雷のlive値・残量ではない。
- tooltip定義を追うと、speedには`CC.parameter`による代替値経路がある。キー候補は`<ownerEntityId>_torpedoSpeed`（alternative/deepwaterは対応する別parameter名）。取得できたParameter entityがあればGUIは`parameter.currentValue`を表示し、delta欄には`currentValue - baseValue`を使う。entityがなければTTXの`speed.value`と`speed.delta`へfallbackする。従ってB15の`75/0`だけではtooltipの補正後speedを確定できない。
- 同tooltipの`maxDist`行には`_alternativeValueKey`がなく、そこでの値sourceは選択TTX variantの`maxDist`である。Battle ship-params画面には別途`torpedoMaxDist`等のparameter名があるが、それをこのammo tooltipの補正後最大射程と同一視しない。
- 抽出GUIの`Components.xml`で飛翔Torpedoのcomponent一次定義を確認したが、`bornTime`、lifetime、remaining rangeのfieldは見つからなかった。`Torpedo`は`id/ownerID/shotID/depth/type`だけを列挙する。これはこの抽出範囲での未確認であり、ゲーム内部に値がない・他component/APIから取得不能という結論ではない。TTX maxDist、観測累積距離、速度×経過時間から残量を合成しない。
- DSFF無料枠中断後に引き継げる保存済みのDSFF固有調査成果は、正本内では確認できなかった。本書は読めたローカル抽出資料とB15記録に基づく通常Lunaでの続きである。

## 調査範囲と根拠

参照した外部抽出rootは`../mino-smoke/research/extracted/gui`。抽出物のbuild・鮮度・完全性は今回独立に検証していない。抽出GUIはPython/dataHubの公開契約でも、ゲーム内部の全実装でもない。今回指定された`C:/Program Files (x86)/Steam/steamapps/common/World of Warships/bin/13357625/res/scripts.zip`の実在とサイズ（53,961,245 bytes）を確認した。ZIP一覧は5,726 entriesで、対象の`.unbound` GUIファイルは含まれず、作業領域にも抽出GUI実体がない。関連するdataHub/Parameter/weapon pycの限定entryだけを読み、Python 2系magic `03f30d0a`の先頭headerとASCII印字可能文字列を確認したが、owner sourceを判定できる識別子は得られなかった。pycは実行せず、Python 3 marshalで読まず、逆コンパイラ・依存導入・大量展開もしていない。

### Tooltip補正値

| 根拠 | 静的に読めること | 取得可否・未確定点 |
|---|---|---|
| `unbound2/pc/ttx/ammos/ammo_torpedoes_tooltip.unbound` L70-L100 | 共通battle macroはTTX `torpedoTTX.maxDist`をkm表示（L85-L88）、`torpedoTTX.speed`をknots表示し、speed行だけ`_ownerEntityId + '_' + _torpedoSpeedParamName`をalternative keyに指定（L93-L97）。 | maxDistはこのtooltip行でparameter overrideを要求していない。speedは補正値候補lookupあり。表示単位ラベルの根拠でありrawデータの単位変換を保証しない。 |
| 同ファイル L104-L150 | 標準・alternative・deepwater layoutはそれぞれ`shipTTX.torpedoes.torpedo/torpedoAlt/torpedoDeepwater`を参照し、speed keyを`torpedoSpeed/torpedoSpeedAlt/torpedoSpeedDeepwater`へ分岐。 | variantからキーへの対応は静的に特定できる。現在の選択TTX descriptorからtooltip側owner entity IDやparameter entityが実際に解決されるかは未観測。 |
| `unbound2/pc/ttx/elements/ttx_params_elements.unbound` L12-L15 | alternative keyがtruthyなら`$datahub.getPrimaryEntity(CC.parameter, key)`、そうでなければnull。 | UIの取得関数・collection/key候補は判明。Pythonから同じ関数を使える保証、CC定数/API可否、keyの実値は未確認。 |
| `unbound2/pc/ttx/elements/values/ttx_value_elements.unbound` L5-L13、L113-L125 | alternative entity有り: 表示値=`parameter.currentValue`、alternative delta=`currentValue - baseValue`。deltaが0なら表示deltaはTTX entryの`.delta`へfallback。entity無し: 表示値=`TTX.value`、delta=`TTX.delta`。 | 補正値の選択規則は読めるが、B15ではparameter entityを採取しておらず補正後の実値・deltaは未取得。表示丸め/他のUI段階は別途未確認。 |
| `data/Components.xml` L1558-L1565 | `Parameter` componentのpropertiesは`ownerID:EntityId`、`id:String`、`baseValue:Number`、`currentValue:Number`。 | GUI alternative keyは複合文字列だがcomponentのprimary key定義との結合方法・Python raw shapeは未確認。型定義だけでcollection取得可能とは言えない。 |
| build 13357625 `res/scripts.zip` 一覧と限定pyc確認 | ZIPは実在。`scripts/ModsShell/API_v_1_0/dataHub.pyc`、`scripts/dh/DataHubExtended.pyc`、`scripts/mcb5884c1/parameters/ParameterSystem.pyc`、`scripts/dhcomponents/Parameter.pyc`等の対象entryは一覧に存在し、確認したpyc headerはPython 2系magic `03f30d0a`。 | `getEntityCollections('parameter')`がPython側で利用可能か、component `id`が複合keyか、`ownerID`のnamespaceは文字列調査だけでは判定できない。marshal解析・実行はしていない。 |
| `data/constants/battle.xml` L754-L769、`shared_constants.unbound` L1104-L1113 | parameter名候補として`torpedoMaxDist`、`torpedoSpeed`、`torpedoSpeedAlt`、`torpedoSpeedDeepwater`等を定義。 | 名前の定義は値の供給entity/valueが実在する証拠ではない。`torpedoMaxDist`はspeed overrideの静的経路と別。 |
| `docs/VALIDATION_0.3.9_B15_TTX.ja.md` L6-L10、L44-L63、L67-L69 | 0.3.9 B15: selected torpedo 137 stateでTTX 75.0/0、9.0/0。画面報告75kts/9kmと一致。`ammoParams`は通常162 stateで空dict。 | B15のprobeに`CC.parameter` lookup/currentValue/baseValueは含まれず、tooltip overrideの有無は判定できない。`ammoParams={}`もparameter経路の不存在を示さない。 |

**現時点の項目別判定**

| 項目 | 静的根拠 | 取得判定 |
|---|---|---|
| 選択TTXのspeed/maxDist | `TorpedoTTX.speed/maxDist:FloatDiff`（`data/structs/ttx.xml` L151-L161）、TTX表示経路。B15でUndine `torpedo`のraw取得・画面数値一致あり。 | 当該条件のTTX候補は取得・照合済み。補正後live値ではない。 |
| Battle tooltip speed override | 固定`CC.parameter` keyと`Parameter.currentValue/baseValue`を読むGUI経路あり。 | Python診断・B15記録に値なし。overrideの実在・取得可否・75からの変化量は未確認。 |
| Battle tooltip maxDist override | 当該ammo tooltipはTTX `maxDist`を直接渡し、別alternative keyなし。別画面のparameter定義は存在。 | 当該tooltipに対するoverride sourceは今回確認できず。全画面・他版でoverrideがないと一般化しない。 |
| 飛翔中の残射程 | `Torpedo` component定義（`Components.xml` L2277-L2286）に残距離fieldなし。`Distance.distanceToShip`等は別component（L2335-L2342）で意味・entity対応未確定。 | 直接値未確認・未取得。`maxDist - observedDistance`は不可。 |
| 飛翔中の残存寿命／bornTime | 同じ`Torpedo`定義に時刻/lifetime fieldなし。 | 一次定義・API供給sourceとも未確認。`WaveHit.lifeTime/maxLifeTime`（L2111-L2121）はWaveHit componentであり魚雷寿命ではない。 |

### 飛翔魚雷と残量候補の限定検索

- `Components.xml` L2277-L2286の`Torpedo`は`id:String`、`ownerID:Integer sync=false`、`shotID:Integer sync=false`、`depth:Number sync=false`、`type:String`、type変更event。定義上、位置・速度・bornTime・経過時間・残距離・残寿命は含まない。
- 同ファイル L1993-L1999の`TorpedoControl`は`sync=false`で照準/表示関連booleanだけ。魚雷個体寿命の証拠ではない。
- `Distance` componentの`distanceToShip`と`distanceToShipBW`（後者はBigWorld meters注記あり）は、魚雷entity上にあることも、発射起点からの消費距離／残射程であることも今回確認できない。現在実装の`observedDistance/Age`も観測開始後の差分累積値で、発射時点・総寿命と結合されていない（[P1_CODE_RESEARCH.ja.md](P1_CODE_RESEARCH.ja.md) L54-L60、L104）。
- 限定検索語は`bornTime`、`lifeTime/maxLifeTime`、`torpedoMaxDist/torpedoSpeed`、`remaining range`候補。今回読んだGUI定義では魚雷個体のborn/lifetime/残量sourceに到達しなかった。GUI外のPython実装、未抽出component、別API、同期外の内部属性は調べ切れていないため、取得不能と断定しない。

## Owner source追跡とparameter probeの判定

**訂正（owner source）**：前版の「中間ファイル実体がなくowner未特定」は誤り。親セッションがowner参照を実読確認した。正本資料rootは`C:/Users/kitta/Documents/playground/wows-mods/mino-smoke/research/extracted/gui`（抽出物build/freshness/completenessは独立未検証）。`unbound2/pc/battle/weapons_panel/slots/slot_renderer.unbound` L20-L21は`weaponType AIRPLANES ? getPrimaryEntity(ownSquadron, squadId) : getSingleEntity(CC.playerAvatar)`として`ownerEntity`を選択する。L291-L292はtooltip viewDataの`_entityId=ownerEntity.id`を設定する。`unbound2/pc/battle/weapons_panel/tooltips/weapon_slot_tooltip.unbound` L37は`BattleAmmoParameters _ownerId=_entityId`。`unbound2/pc/ttx/ammos/ammo_tooltip_adapter.unbound` L36-L51はこれをrendererへ渡し、`ammo_torpedoes_tooltip.unbound` L93-L97が`_ownerEntityId + '_' + torpedoSpeedParam`を作る。`ttx/elements/ttx_params_elements.unbound`はparameter primary lookupへキーを渡し、`ttx/elements/values/ttx_value_elements.unbound`は`currentValue/baseValue`とfallbackを定義する。よって通常のnon-airplane魚雷slotのGUI owner sourceは**playerAvatar entity.id**と特定できる。Pythonから同じcollection/APIが取得できることやairplane routeは保証しない。

namespaceも分けて扱う：GUI lookup keyは`<ownerEntityId>_<parameterName>`という複合文字列。一方、抽出`Components.xml` L1558-L1565ではParameterのPKは`(ownerID: EntityId, id: String)`。B18の実測rowも`id`がparameter名単独で、対象rowの`ownerID`はplayerAvatar entity.id候補と139/139 strict一致した。この条件に限るraw selectorは2 fieldを比較する。GUI keyの内部encodingとowner namespaceの一般同一性は未確定で、他variant/buildへ一般化しない。weapon slotの`id`、ammo componentの`id`、selfVehicle entity ID等を推測で結ばない。

**現時点の取得route判定：**owner sourceはGUI上でplayerAvatar entity.idと特定済み。Python probeは成功かつ完全singletonのplayerAvatar `entity.id`だけowner候補とし、parameterは固定key/field whitelistで最大64行を読む。`selectedParameter`は`component.id == parameterName`かつ`component.ownerID == ownerEntityId`のraw strict composite候補一致が一意で、collection/required fieldが完全な場合のみavailable。GUI形式の合成keyは診断metadataのみでcomponent `id`と混同しない。GUIの`getPrimaryEntity`はPython側probeで呼び出さず、その内部encodingを再現したとは主張しない。

0.3.10で追加した**実装上の保守的ルール**（探索は診断専用、通常値へ昇格しない）：

1. owner候補は成功・単一・completeな`playerAvatar` collectionから読んだ`entity.id`のみ。descriptorに対応するspeed parameter名は固定対応表から一つ選ぶ。owner scalarからUI同等のkey候補を作れない場合はkeyを出さない。
2. `getEntityCollections('parameter')`は最大64 entity、component keyは固定`parameter`のみ。各entityでは`id`候補とcomponentの`ownerID/id/baseValue/currentValue/source/status/type`だけ。全属性列挙・他collection走査・GUI getter fallbackなし。getter/key/call/component/field stageを分ける。
3. 複合PK両fieldがavailableかつ有効で、候補とのstrict不一致が確認できるrowだけ除外可能。欠測/不正/truncated fieldのrowがあればincompleteとしてunknown。候補複合PKがduplicate、collectionがpartial/truncatedの場合もunknown。数値はfinite・bool除外・±1,000,000以内。
4. parameter候補はTTX rawと別sourceで維持する。TTX上書き、delta加算、live速度確定、残距離/寿命推定には使わない。毎snapshot独立でhistoryなし。

GUI根拠が確認できたためprobe実装へ進んだが、Python取得実績はまだない。route unknownは取得不能の証明ではない。

## 残射程・寿命の次段階

**飛翔中残射程・寿命はparameter diagnosticに混ぜない。** 今回のscripts.zip限定一覧・対象pyc header/文字列調査から、`bornTime`、`lifeTime/maxLifeTime`、残射程を供給するPython公開field/routeは確定できなかった。これはpyc中に存在しない、または取得不能という結論ではない。GUI `Torpedo` component一次定義に直接値が見つからないという既存範囲も維持し、GUI外のsimulation/API実装は未確認とする。`getAllTorpedoes`/UI collectionのwhitelist拡張や観測累積値だけでは直接残量の根拠にならない。残射程・寿命は直接sourceが別途特定できるまでunknownとして保留し、次のP1静的調査は潜水艦関連（深度・潜航/浮上状態等）の公開取得候補へ進める。実測挙動だけから直接値を逆算しない。

## P1の着地点と未確認範囲

- **今回の着地点**：GUI ownerはplayerAvatar entity.idと読めるが、Python側collection/field/valueは未確認。0.3.10 bounded probeは成功した単一playerAvatar entity.id候補と固定parameter raw field候補を分けて記録し、exact shape以外をunknownにする。残射程・寿命の直接sourceは未特定として保留し、次はP1潜水艦関連候補へ進める。
- **最短実機確認**：Undineで魚雷を選択しtooltipを約10秒保つ。mod reload/発射不要。`torpedoTooltipParameterProbe`のowner/collection/stage statuses、selectedParameter reason/fieldsを確認し、画面表示が75kts/9kmならメモする。route診断であり補正値の意味は確定しない。
- **未確認**：抽出物の正確なbuild/完全性、Python `playerAvatar`/`parameter` collection可否・shape、Python ID scalar spelling、GUI keyと`Parameter.ownerID/id` namespace対応、Parameter entity/value/update時系列、override値、tooltip全renderer条件、TTX補正要因と丸め、残射程/寿命を供給するGUI外API・simulation定義・出生時刻。今回ゲーム起動・pyc実行・依存導入・ZIP生成・ゲーム導入はしていない。

## 関連資料

- [RESEARCH_SELECTED_TORPEDO_PARAMS.ja.md](RESEARCH_SELECTED_TORPEDO_PARAMS.ja.md)：TTX候補のroute、descriptor/variant選択、raw値の扱い。
- [VALIDATION_0.3.9_B15_TTX.ja.md](VALIDATION_0.3.9_B15_TTX.ja.md)：Undine、75/9画面一致、`ammoParams={}`の実機記録。
- [P1_CODE_RESEARCH.ja.md](P1_CODE_RESEARCH.ja.md) L54-L60、L77-L104：現行魚雷運動・観測累積値とP1優先順。
- [res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py](../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py)：現行whitelist/API候補。今回変更なし。
