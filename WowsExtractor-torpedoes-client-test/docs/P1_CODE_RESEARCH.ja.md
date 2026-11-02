# P1コード調査：収集層・魚雷・装填

調査対象はmod 0.3.2のソースと、親セッションで指定されたローカルGUI抽出資料に限定する。これは静的コード調査であり、ゲーム内取得や意味の検証を完了した報告ではない。目標は、魚雷戦に必要な情報を取得状態・由来・単位とともに出力する収集層の完成。最終目撃履歴、失探判定、保持期限、ghost生成はマップアプリ側の責務とする。

## 判定の読み方

- **静的確認**：ソース／抽出定義に名前や参照経路が存在すること。実行時にアクセス可能、またはゲーム内で正しい意味を持つことの証明ではない。
- **取得確認**：対象build・実行環境で値が読み出せたこと。値の意味・単位・対象との対応は別に検証する。
- **意味確定**：操作、UI、対象、時刻を独立に照合し、仕様として採用できた段階。
- API doublesを使うpytestは変換ロジックの確認であり、ゲームエンジン／ModsAPIの実取得根拠ではない。

## 1. 収集層への整理

可視フラグの標準UIでの参照先、ゲーム由来最終発見時刻の限定調査、取得限界、
診断仕様および1試験の手順は [`VISIBILITY_RESEARCH.ja.md`](VISIBILITY_RESEARCH.ja.md)
を参照。調査結果の要約：GUIは`mapVisible`と`visible`を別々に使うが、その用途は
当該UIの表示ロジックに限られ、サーバー発見状態の意味確定ではない。指定された
クライアントpycはPython 2系形式で、実行・誤ったPython 3 marshal解析を避けたため
API中身は未確認。最終発見時刻の取得可否はunknown。

### 現行実装

- 現行方針では独自の最終目撃時刻・TTL・ghost生成を持たない。0.3.2の変更記録と実機報告は [`OBSERVATIONS.ja.md`](OBSERVATIONS.ja.md#L5) にある。今回確認した `Main.py` の出力組み立て（[L1168-L1207](../res_mods/PnFMods/WowsExtractor/Main.py#L1168)）は現在スナップショットのself／ships／魚雷／armament等をまとめる経路で、古い座標の履歴を再生成していない。
- ただし「残存する派生値やキャッシュを全撤去した」とは言えない。魚雷の位置差分motionと地図較正は現行処理であり、戦闘開始・終了でmotion／較正をclearしている（[Main.py L748-L818](../res_mods/PnFMods/WowsExtractor/Main.py#L748)）。`ui_health.py` L120-L125にはghost／last-seenを前提とした旧コメントも残る。コメントは実装の証拠ではないが、整理の別途確認箇所として記録する。
- 0.3.3では`visibility.raw`互換値を維持しつつ、4つのdataHub visibility候補と2つのship API候補についてsource/raw/type/status/reasonを候補別に出す。statusはfalse取得・欠落・None・読取例外・非bool・component/CC key状態を区別し、rawは有限なbounded scalarに限定する。実機取得・意味は未確認。出力投影は引き続きmapVisibleに基づき、意味は`unverified`。取得座標はvisibility=falseだけで捨てず、falseの行は較正対応点から除く。
- 船のworld position抽出では `shipGameData.x/z` の組に `y=0.0` を補う経路がある（[Main.py L1244-L1296](../res_mods/PnFMods/WowsExtractor/Main.py#L1244)）。地図較正の `map_to_world` も `[worldX, 0, worldZ]` を返す（[map_calibration.py L529-L544](../res_mods/PnFMods/WowsExtractor/map_calibration.py#L529)）。このy=0は深度ではない。船のyawはmapPositionからfallbackする場合があるが、出力に値の由来を併記していない（Main.py L1517-L1526）。自艦のshipGameData `speed`／`yaw` 等はコピーされる（[Main.py L1216-L1242](../res_mods/PnFMods/WowsExtractor/Main.py#L1216)）が、ここで単位・座標軸は確定しない。

### 静的資料と既知の限界

- 作業ルートから見た `../mino-smoke/research/extracted/gui/data/Components.xml`（リポジトリ外、読み取り専用）では `Visibility.visible`／`mapVisible` がBoolean（L1297-L1301）。この抽出物の由来メモは `../mino-smoke/research/FEASIBILITY.ja.md` L9にあり、build 13357625のidx/res_packagesから抽出した記録。ただし今回再抽出・ハッシュ照合はしていない。該当抽出物内で最終発見時刻プロパティは見つけられていないが、ゲーム全体に存在しない証明ではない。
- `visible`、`mapVisible`の名称やBoolean型だけからサーバー発見状態を断定しない。現行0.3.2の実機取得確認（mapVisible true/false、座標保持）は [`OBSERVATIONS.ja.md` L34-L49](OBSERVATIONS.ja.md#L34) に記録済みだが、操作・対象との厳密な対応は未確定。
- **実機未確認候補**：診断追加版では `mapVisible/visible/isVisible/isShipVisible` の候補status/raw/type/reasonを個別出力する。`visible`を含む新診断の実機取得・対象との対応・意味は未確認。`mapVisible`の0.3.2実機値取得済みと、この別属性`visible`の意味未確認を混同しない。
- pytestの回帰箇所：[test_visibility_observations.py L18-L50](../tests/test_visibility_observations.py#L18)、[test_map_calibration.py L211-L250](../tests/test_map_calibration.py#L211)。これらはfixture／擬似入力のテストで、実機取得証拠ではない。

### 次に確認すること

1. 表示されている艦・失探／再発見操作の正確な時刻を記録し、`mapVisible`、座標、対象playerIdを同じ戦闘記録で突合する。意味が確定するまで `semantics=unverified` を維持する。
2. ゲーム由来の最終発見／可視時刻について、GUI参照とクライアント `res/scripts.zip` の指定pycを限定調査した。pycエントリとPython 2系ヘッダは確認したが、環境に既存逆コンパイラがなく、実行・誤解析・依存導入を避けたため中身・署名は未解析。GUIにも艦の時刻参照は見つからず、未公開経路は引き続きunknown（詳細は[可視調査](VISIBILITY_RESEARCH.ja.md)）。
3. 0.3.3で限定診断を実装済み。次は候補status/rawと標準UIを対象ID・操作時刻で実機照合する。意味は`unverified`とし、値が無いことをfalseや時刻0に置換しない。最終発見時刻の直接フィールドは取得元・時刻基準が確認できるまで追加しない。

### MeatProxy試験案：可視候補と座標

目的：既に取得確認済みの`mapVisible`と座標の操作対応を記録し、診断追加後にのみ`Visibility.visible`候補の有無・遷移も評価する。取得不能な項目を出力しない旧版の記録から、その項目の挙動を検証したことにはしない。

1. **準備**：mod 0.3.2、ゲームbuild、ATM有無を記録。可能なら訓練環境で味方協力者を用意し、Minotaur／Undine等で対象艦が自艦3D視界外でもミニマップ表示される条件を作る。戦闘・対象識別に必要な情報だけをメモし、個人情報を含むログ共有は避ける。
2. **現行版でできる操作**：対象艦が表示中の状態を記録→島影等で自艦視界から隠す（味方発見が続く条件も別記）→対象がミニマップから消える／再表示される条件を作る→同じ対象を再発見する。各操作の壁時計時刻、対象識別子、ゲーム内表示を記録する。`mapVisible`、`visibility.raw`、`mapPositionRaw`の取得と遷移は評価できるが、厳密な発見意味は確定しない。
3. **候補診断追加後に行う操作**：出力に`Visibility.visible` raw値・型・取得statusが含まれることを事前確認してから、同一手順を再実施する。診断追加前の記録はこの属性を含まないため、遡って値・遷移・取得不能理由を判定できない。
4. **採取物と判定**：完全jsonl、meta／modログ、mod版・build・ATM有無、操作タイムライン、可能ならゲーム内表示の画像。対象ID単位で`visible`と`mapVisible`の値・欠測・型、座標保持、一覧有無を照合する。取得status availableは値の意味確定を意味しない。操作／対象との対応が不十分なら`semantics=unverified`のままにする。

## 2. 魚雷識別・運動・単位

### 現行実装

- [torpedo_telemetry.py L20-L23](../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py#L20) の明示フィールドは `uiId/ownerId/ownerTeamId/ownerType/shotId/type`。`getAllTorpedoes` の行にpositionを付加し、`ownerId` をそのまま `getTorpedoOwnerById` に渡す（[L295-L325](../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py#L295)）。所有者APIの `isPlayer` が真偽値のときだけ `isOwn` を出し、それ以外はnull。teamIdによるrelationは味方／敵チーム候補であり、自艦魚雷の確定ではない。
- `ownerId/ownerTeamId/ownerType`は実機取得済みで、0.3.1記録では`ownerId` 374/374行、`ownerTeamId`／`ownerType`も取得確認済み（[SPEC_COVERAGE_0.3.1.ja.md L34-L36](SPEC_COVERAGE_0.3.1.ja.md#L34)、[ACQUISITION_STATUS.ja.md L52-L59](ACQUISITION_STATUS.ja.md#L52)）。一方、`ownerId`とplayerId／vehicleIdのnamespace対応は未確定。owner objectの一部属性（特に`isPlayer`等）はnullで、`isOwn`判定は成立していない。値取得と識別意味を分け、名前空間を推測joinしない（[test_torpedo_telemetry.py L46-L56](../tests/test_torpedo_telemetry.py#L46)）。
- `public_data` は公開属性を `dir()` から読み出すが、読み出し失敗を個別に識別せず安全化する（[torpedo_telemetry.py L55-L96](../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py#L55)）。一部SafeClassが空 `{}` になる可能性は調査対象。API呼び出し例外も `_call` では `unknown` にまとめる（L103-L111）。
- UI診断はdataHubの `torpedo` collectionを最大64件、公開 `dataKeys` を最大32件調べる。`type`、`isHoming`、`isSpotted`を取得候補として保持し、API `uiId` とentity ID候補が一意一致した時のみjoinする（[L114-L205](../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py#L114)）。現行docstringの「Python可用性未試験」は過去の記述で、0.3.1記録にはUI側type／entity IDの実機取得、ATMありの`isHoming`実機取得、`isSpotted=true`の実機取得がある（[ACQUISITION_STATUS.ja.md L61-L74](ACQUISITION_STATUS.ja.md#L61)、[SPEC_COVERAGE_0.3.1.ja.md L55-L63](SPEC_COVERAGE_0.3.1.ja.md#L55)）。ただしATMなしでの`isHoming`欠損や`isSpotted=false`未観測などの制約は残り、probe一般の全条件での可用性・意味を保証しない。
- 現行運動値は同じ `uiId` と `(ownerId, shotId)` が維持され、`0 < dt <= 1s` の位置差分がある時だけ算出（[L208-L257](../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py#L208)）。速度は水平XZ距離÷dt、headingは `atan2(vx,vz)`、velocityはXYZ成分。単位ラベルは `game_world_units_per_second` で、ゲーム表示のノット等への換算はしない。`observedDistance/Age` も取得開始後の水平累積距離／経過秒であり、魚雷の残り射程・寿命ではない。
- `uiId`の再利用、複数斉射間の`shotId`共有範囲、魚雷の途中参加・消失、owner APIのnull時の意味は未検証。深度値は現在の明示フィールドに含まれない。`type`をhomingに読み替えていない（[test_torpedo_telemetry.py L123-L132](../tests/test_torpedo_telemetry.py#L123)）。
- `_build_state`でUI state／motion／mapPositionを合成する（[Main.py L1168-L1207](../res_mods/PnFMods/WowsExtractor/Main.py#L1168)）。`now` は `utils.getTimeFromGameStart()` 由来（[Main.py L227-L229](../res_mods/PnFMods/WowsExtractor/Main.py#L227)）。戦闘開始／終了でmotion履歴をclearする（[Main.py L748-L818](../res_mods/PnFMods/WowsExtractor/Main.py#L748)）。時間基準・座標単位そのもののゲーム仕様までは確認していない。

### 静的資料と次の調査

- 作業ルートから見た `../mino-smoke/research/extracted/gui/data/Components.xml` のTorpedo component（L2277-L2286）は `id:String`、`ownerID:Integer`、`shotID:Integer`、`depth:Number`（これら3属性は`sync=false`）、`type:String`を定義する。抽出定義上は`ownerID`、API上は`ownerId`という異なる綴りを確認できるが、API側の型や両者の対応をこの資料からは確定できない。`sync=false`からPython可用性を推定しない。
- 同資料の抽出鮮度は上記の通り未再照合。作業ルートから見た `../mino-smoke/research/extracted/gui/unbound2/pc/battle/weapons_panel/slots/slot_renderer.unbound` L67-L69はslot stateとRELOAD/CRITICAL等のUI比較を示すが、魚雷collectionのPython取得根拠ではない。
- 次の静的確認先は `res/scripts.zip` のModsAPI wrapperとdataHub公開メソッド。名前空間の実値、返り値、`None`／例外の意味を確認する。Python側で取得できなければunboundのentity/componentを次候補にするが、UI定義だけで取得可能とは判定しない。

### MeatProxy試験案：識別と運動

目的：推測joinなしで自艦魚雷のowner識別、UI候補値、複数斉射と欠測時の挙動を実測し、ゲーム内速度・角度表示と推定値を比較する。

1. **準備**：mod 0.3.2、buildを記録、ATMなしを基本とし、可能なら同じシナリオのATMありを別記録で実施。Minotaur／Undineを使う。安全に魚雷を観察できる訓練環境・味方協力者を選び、マップ・艦・魚雷本数、ゲーム内表示の撮影可否を記録する。ゲームを変更する操作は行わず、通常の既存record手順を使用。
2. **操作**：停止中に発射→直進中を記録→可能なら転舵／誘導切替→二斉射目を発射→画面外／他者魚雷を観察→記録可能な範囲で消失・再登場まで継続。記録者は各操作の壁時計時刻と対象魚雷を別メモにする。操作や味方協力ができない項目は未実施とする。
3. **採取物**：完全なjsonl記録、meta／modログ、mod版・ゲームbuild・ATM有無、艦・環境、操作タイムライン、ゲーム内速度／角度表示のスクリーンショット（可能な場合）。個人ログを共有する場合は本人確認の上で必要部分のみ。
4. **判定**：同一魚雷の連続 `uiId/ownerId/shotId/type/position`、owner lookupと`isOwn` status、UI probeの対応・重複・64件上限、motionの`dt`／水平速度／headingを追跡。停止・旋回・1秒超gap・消失・再取得・ID再利用を区別する。表示値との一致で単位を確定するには複数の安定区間と独立した時間基準が必要。単一試行や名前一致では意味確定にしない。

## 3. 装填・魚雷性能

### 現行実装

- 現行の `armament()` は `getTorpedoesModulesState()` からmoduleの `type/currentHP/maxHP/state/critTimer` とpositionだけを採取し、選択中弾薬は `getSelectedAmmoId(WeaponType.TORPEDO)`、属性は `getAmmoParams(id)` を `public_data` に通す（[torpedo_telemetry.py L327-L359](../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py#L327)）。残数、管別装填残時間、発射可否を直接出す現行API経路はここにない。
- `getAmmoParams`成功でも内容が `{}` ならstatusはavailableとなり得る。これは取得処理が成功した状態であって、性能値が取れた意味ではない。`public_data`によるSafeClassの公開属性列挙が空になるかも未確定。
- 回帰テストでは擬似ammoの `torpedoSpeed` を含む公開属性をコピーできることを確認するだけ（[test_torpedo_telemetry.py L86-L112](../tests/test_torpedo_telemetry.py#L86)）。ゲーム由来の実性能値や単位は未確認。

### 静的GUI資料（候補であって取得実績ではない）

作業ルートから見た `../mino-smoke/research/extracted/gui/data/Components.xml` は以下を定義する（抽出元build・鮮度の制限は前掲）：

- 戦闘時計UI式は `../mino-smoke/research/extracted/gui/unbound2/pc/battle/battle_timer.unbound` L5-L8: `CC.battleTimer` entityを取得し、`battleEntity.battleTimer.battleTime`を読み、`battleEntity.battleInfo.duration * 60`から差し引く（L12でcountdown表示に使用）。これはUIが表示式に使う参照の静的根拠であってPython/dataHub公開契約や、collection routeのentity同一性を保証しない。B11の10分duration・約20秒のbattleTime・ユーザー報告9:40とは今回の試験条件で整合した。

- `Weapon` state、`Gun` type/index/state/status、`GunsGroup`、`ReloadModifier.duration`、`SerialLoaderModifier.serialLoads`、`ReloadBar`（L1784-L1914）。`WeaponSlot`は `type/state/active/selected/shotCount` 等を持ち、`ammoParamsId` と `ident` は `sync=false`（L1924-L1944）。`GunsCount`には `countReloadedGuns/countActiveGuns` があるがcomponent自体もsync=false（L1967-L1972）。これらの定義だけではdataHubでどのentity/componentから読めるか、値の単位・更新意味は未確定。
- `ttx.xml` の `TorpedoTTX` は `damage/visibility/maxDist/speed` を `FloatDiff`、`TorpedoesTTX`／launcher/groupは `reloadTime/ammoSwitchTime/numLoaders` 等を定義（L151-L193）。性能表／比較表示用候補であり、実際の船・選択弾薬・補正後値との対応や `FloatDiff` のshape・単位は未確認。
- **訂正（重要）**：slot進捗は`slot.progress`というweaponSlot componentの属性ではない。UIコードは`slot.progress.value/max`と書くが、`slot`は同一entityで、`progress`は独立した`CC.progress` component（`Components.xml`のProgress定義）として参照される。serialLoadも`entity.progress`の同じ別component。`weaponSlot` componentから架空の`progress`/`ammo`を読んではならない。
- `SerialLoaderInfo`は`CC.serialLoad` collectionを`byWeaponType`／weapon typeで引き、各entityの`serialLoad.state`と同じentity上の別`progress.value/max`を表示する（`slot_serial_loader_info.unbound` L3-L35）。weapon tooltipは独立した`CC.ammo` entityを`slot.weaponSlot.id`で`getPrimaryEntity`し、その`ammo.viewData`を表示する（`slot_renderer.unbound` L16-L24、L285-L303）。tooltip本体はviewDataのtitle/description等とparamsDescriptorを描画する（`weapon_slot_tooltip.unbound` L3-L15、L21-L38）。このUI上のjoinはPython公開契約ではない。`limitedAmmo` current count（slot_renderer L36-L41）はsecondary ammo用で、魚雷残数の根拠にはしない。
- 0.3.4は`weaponSlot`／`ammo`／`serialLoad` collectionとCC component key候補をread-onlyで独立診断する。slotの`progress`は同一entityの`CC.progress`; serialLoadも同様。ammoは別配列のままでID joinしない。各collection最大32行、固定field whitelist、有限scalar／安全なcontainer限定。`shotCount`はraw候補で残弾とは断定しない。`progress.value/max`もraw候補で残秒・割合とは断定しない。`serialLoad`は`index/weaponType/state`と別progress、entity ID候補を出す。ammoは`id`候補とviewData固定属性／paramsDescriptor候補だけ。新collection/key名の公開契約、getter実機可用性、型shape、意味はいずれも未確認。

### 次の調査とMeatProxy試験案

1. **静的優先**：`res/scripts.zip` のShip／dataHub wrapperと、上記slot renderer／reload bar／tooltipの参照元を照合する。`getTorpedoesModulesState`、`getAmmoParams`、`ammoParamsId`、`CC.serialLoad`、`ReloadModifier.duration`、`shotCount`、`endTime`、`currentTime`を検索語とする。コンポーネントの存在から取得APIを推測して実装しない。
2. **現行版でできる試験**：現在すでに出力されるmodulesのtype/HP/state/position、selectedAmmoId/status、ammoParams/statusを記録する。満装填→魚雷切替→1本発射→再装填→完了の順に、各時刻と発射可否・UI残り表示・選択弾を記録する。これら既存出力でmodules状態やammoParamsの応答は照合できるが、出力にない管別残数・残秒・発射可否値・TTX値が取得不能でも、その値や意味を検証したことにはならない。`ammoParams={}`は属性取得不能／空結果として記録し、性能値の試験成功とみなさない。
3. **診断候補追加後の試験**：静的経路を基に候補値を限定して診断出力へ追加した後、導入版・build・ATM有無を記録して同じ操作を再実施する。診断候補は意味未確認であることをstatus/source/`semantics=unverified`等で明示し、欠測をfalse/0に置換しない。診断に出ていない項目は試験で検証不能なので、先に項目を追加するか、取得不能として記録する。
4. **故障・修理試験**：訓練環境で可能な場合のみ、管の被害・修理を通常装填とは別条件・別タイムラインで実施する。`critTimer`とUI repair/reload countdownの対応を比較し、故障タイマーと装填タイマーを同一視しない。
5. **採取物と判定**：完全jsonl、meta／modログ、艦・ammo UI名称、魚雷性能表示（速度・最大射程）、slot別UIと操作時刻メモを保存。API／診断値の変化を選択切替／発射／修理と照合する。TTX比較値は実測挙動と分け、値のshape・単位・補正を確定するまで「性能表候補」とする。管単位を識別できない場合は未取得とし、船全体の残数から補完しない。
6. **残り射程・寿命**：現行 `observedDistance/Age` は取得開始後の差分累積値であり、魚雷残り射程／寿命ではない。直接API値が確認できない限り残量を出さず、性能×経過時間等の推定を将来行う場合も直接値とは別フィールド・明示的推定に限定する。

## 優先順

1. `res/scripts.zip` の限定的な公開API/dataHub調査（owner namespace、SafeClass属性、装填値、既知probe取得条件の現行buildでの再現性）。
2. 現行出力で取得できる魚雷識別／運動／ATM差分と装填関連フィールドをMeatProxyで試験する。結果が欠ける対象は未取得として残し、欠けたまま意味検証済みとしない。
3. 取得できていない候補（`Visibility.visible`、管別progress／残秒、性能descriptor等）は意味未確認・unknown/unverifiedラベル・取得元・型を明示した診断として追加する。
4. 診断を含む版をMeatProxyが実機試験し、候補値の利用可否・操作との対応を確かめる。修理／故障は通常装填と別条件。
5. 実測後に取得status/source/単位/推定区分/根拠を整理し、出力契約と通常出力へ確定反映する。診断候補の追加→実機取得→意味検証→契約確定の順とし、意味が未確定なことを理由に診断実装を先送りしない。

今回、ゲーム起動、mod導入、ソース実装変更、記録再生／再生成、外部抽出物のコピーは行っていない。

### 0.3.4の診断試験（実機未確認）

Minotaur訓練戦で導入版・ゲームbuild・ATM有無を記録する。`state.json`の`weaponHubProbe`を確認し、満装填→魚雷スロット選択→単発発射→UI上の再装填進行→再装填完了の順で時刻をメモする。各時点のslot `state/active/selected/shotCount`、同一slot entity progress、serialLoad、ammo viewData候補を比較する。`status=available`は取得成功のみで意味確定ではない。データなし・unsupported/unknown/partial/truncatedを分け、残数・残秒・速度・射程として解釈しない。0.3.3 ZIPおよび既存試験中環境には触れず、次版を別途レビュー後に試験する。
