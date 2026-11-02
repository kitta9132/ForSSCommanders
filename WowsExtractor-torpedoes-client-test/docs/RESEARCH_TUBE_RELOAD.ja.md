# 管別 reload bar の静的経路調査

## 結論

B12の`weaponSlot` rowは、兵装パネルのスロット表示用データとして読むのが妥当で、管別reload barの唯一の情報源ではない。`slot_renderer.unbound`はslot entity上の`weaponSlot`と同じentityの`progress`を使い、選択／activeなスロットの円形progressを描く。一方、`guns_reload_bar.unbound`は`CC.weapon`、`CC.gun`、場合により`CC.groupModifier`／`CC.gunsGroup`を辿り、gun entityまたはbarrel／serial-load entity上の`CC.progress`を個別バーに使う。

よってB12で観測したtype 2 slotの初期45秒進捗は、同一のUI値が管別reload barにも出ている証拠ではない。発射時のstate 8が一瞬でreadyへ戻り、発射後45秒のslot progressがないことも、「個別 gun/barrel 側 progress が存在しない」ことを示さない。`serialLoad`の空列挙は`CC.serialLoad` collection候補が空だったという範囲に限られ、gunの`SerialLoaderModifier.serialLoads`や他gun/barrel progressを調べていない。

次の実機試験前に固定whitelistのread-only診断を追加する。B12の当初「実装修正不要、同試験再実施」という判断は、slot初期装填のみを見て発射後tube reloadに必要なgun UI経路を取得していなかったというcoverage不足が判明したため訂正する。同じ時計・選択確認を重複せず、診断経路追加後に最小の装填試験を一度実施する。

## 範囲と根拠の鮮度

- 正本の照合対象は [`VALIDATION_0.3.7_B12_WEAPONS.ja.md`](VALIDATION_0.3.7_B12_WEAPONS.ja.md)。Undineで残り8:00の単発発射、7:15の装填完了という操作報告に対し、同記録でclockは時系列整合したが、発射後の45秒`weaponSlot` progressは未観測。state 8は1 sampleのみ、`serialLoad` collectionは0 rows。
- 静的資料は作業ディレクトリ外の`../mino-smoke/research/extracted/gui/data/Components.xml`と同ディレクトリの`unbound2/pc/battle`。抽出元build／現行ゲームとの一致は確認していない。UI参照の静的根拠であり、Python `dataHub`の公開契約、実機可用性、entity scope、意味・単位を保証しない。
- 非公式pycは実行していない。ゲーム、mod、依存関係、抽出物は変更していない。

## コンポーネント定義（Components.xml）

| 定義 | 行 | 関連する固定フィールド／含意 |
|---|---:|---|
| `Weapon` | 1784–1795 | `type`、`state`、`iconType`、`groupsCount`。reload bar側がweapon typeのprimary entityを使う。 |
| `Gun` | 1798–1819 | `id`、`index`、`state`、`type`、`position`、`status`等。gunごとのstate/位置を描画に使う。 |
| `GunBarrel` | 1821 | 空component定義。UIは`BarrelsModifier.barrels`に列挙されたIDを`getEntity(id)`してprogressを読む。 |
| `GunsGroup` | 1855–1862 | composite key相当の`type`＋`groupID`、`mostReadyGunId`。グループ内表示代表gunを決める参照。 |
| `ReloadModifier` / `ChargeModifier` | 1873–1877 / 1886–1890 | `duration`（sync=false）。存在は確認できるが、調べたreload bar式はprogressを直接読む。durationは残秒・進捗値として代用しない。 |
| `BarrelsModifier` | 1879–1884 | `barrels` array、`mode`。UIはbarrels長とSINGLE modeを見てバー数を作る。 |
| `SerialLoaderModifier` | 1894–1898 | `serialLoads` array。UIは配列長と各IDのprogress/stateを使う。 |
| `GroupModifier` | 1900–1903 | `groupID`、`reloadBarOrder`。UI collectionの`byWeaponType/byGroup`でgun一覧を分ける。 |
| `ReloadBar` | 1905–1914 | `rowsCount`、`order`、`prevOrder`、`iconName`、`isOutOfBounds`。reload barの行・配置情報で、進捗そのものではない。 |
| `WeaponSlot` | 1924–1946 | slot単位の`id/type/state/active/selected/shotCount`等。component定義にprogressはない。 |
| `GunsCount` | 1967–1973 | `countGuns/countAliveGuns/countReloadedGuns/countActiveGuns`、sync=false。集計候補であり個別管progressではない。 |
| `Progress` | 2540–2546 | `value/min/max`。単体定義のみではownerや単位が分からない。 |

## UIの実際の参照経路

行番号は上記の抽出unboundファイル内。

### weaponSlot表示はスロット全体の別境界

`weapons_panel/slots/slot_renderer.unbound`:

- L6–16: `selfVehicle`からcontrollerを参照し、slotは`getPrimaryEntity(CC.weaponSlot, _id)`。ammoは別に`getPrimaryEntity(CC.ammo, slot.weaponSlot.id)`。
- L62–68: controllerのselected weaponとslotのactive/selected/stateから表示状態を決める。
- **L93–100**: `slot.progress.value/max`でprogressとremain候補を計算し、`slot.weaponSlot.shotCount`も別に読む。
- L208–217: このprogressを`SlotReloadBar`へ渡す。L226ではslotの`evReloaded`に反応。

このUI式上は`slot.progress`がスロットアイコン内の進捗値で、gun entityの管別バーとは異なるentity参照である。slot collectionが取得可能でもgun collection/progressの取得成功を含意しない。slot UIの式にもWORK状態による向きの切替えがあるため、raw progressを常にelapsedまたはremainingと断定しない。

### gun／barrel単位のreload bar

`battle/reload_bar/guns_reload_bar.unbound`:

- L48–80: reload bar root。L51でweaponSlot collectionを表示制御用に取得し、L86–89でcontrollerと**別の**`CC.reloadBar` collectionを使う。
- L106–115: `reloadBar` rowの`weapon.type`をbar rendererへ渡す。
- L163–180: `getPrimaryEntity(CC.weapon, weaponType)`と`weaponEntity.reloadBar`を参照し、gun collectionは`CC.gun`の`byWeaponType`で取る（L177–178）。
- L242–255: 非grouped経路ではgun collectionの各itemを`GunReloadBarRenderer`へ渡し、gunごとのバーを作る。
- L388–435: grouped経路は`CC.groupModifier.byWeaponType.byGroup[groupID]`のgun一覧を使う。`CC.gunsGroup(weaponType, groupID).mostReadyGunId`はグループ代表状態／timer用。通常の各barはgroup list itemのIDをgun IDおよびprogress entity IDとして渡す（L425–432）。
- L438–473: 各gun entityの`gun.position/type/state`を取得。gun同一entityの`BarrelsModifier`があれば`barrels.length`と`mode`から管別バー数を選び、`SerialLoaderModifier.serialLoads`があればserial load数を優先する。
- **L494–504**: serial reload時のprogress entity IDは`serialLoads[index]`、single-barrel fire mode時は`barrels[index]`、それ以外はgun entity ID。したがってIDリストの指すentityを解決した先のprogressを読む経路がUIにある。
- **L551–559**: gun entity上の`CC.progress.value/max`を読む。WORK、damage、RELOAD_STOPPED等でtimer式が変わる。
- **L581–593**: serial entityの`CC.progress.value/max`を使い、repair状態なら`value`、それ以外なら`max-value`を表示timer候補にする。
- **L612–637**: serial entity上の`serialLoad.state`とprogressを組み合わせる。
- L650–665:通常bar adapterも`getEntity(_progressEntityId).progress.value/max`でバー比率を計算する。

UIが組み立てるscopeはweapon type→gun群→個別gun→(必要な場合) barrelまたはserial-load ID→そのentityのprogress。これが管単位候補の最短で根拠ある経路である。barrel/serialLoadのIDから`getEntity(id)`で解決するのはUIコード上の関係であり、Python probeで異なるcollectionをID joinする根拠にはならない。

### serial-load slot情報とcompass

- `weapons_panel/slots/slot_serial_loader_info.unbound` L3–23: `CC.serialLoad.byWeaponType[weaponType]`を列挙。L30–34で各entityの`serialLoad.state`および同一entityの`progress.value/max`を読む。
- `battle/compass.unbound` L267–305: weapon type別`CC.gun`と`CC.gunsGroup`を使い、grouped submarineでは`mostReadyGunId`を選ぶ。L308–321で具体的なweapon entity/gun entityとcontroller selectionを区別する。
- Compassのgun一覧は管のreload progressを列挙するreload-barそのものではないが、gun entity IDとgunsGroup関係をUIが使う独立根拠になる。

## 推奨する最小read-only診断候補

現probeの定数は`torpedo_telemetry.py` L210–217。現在のcollection候補は`weaponSlot/progress/ammo/serialLoad`で、`weaponSlot`のprogressはslot entityから読む一方、`gun`、`reloadBar`、gun modifierは対象外（L297–365、372–407）。次段階は以下に限定する。

### 固定whitelist

| root候補／collection | component key | 固定field候補 | 根拠・結び方 |
|---|---|---|---|
| `gun` collection | `gun` | entity ID candidate; `id/index/type/state/position/status` | UIの`CC.gun.byWeaponType`。gun collection item自身をgun entityとして読む。`type`はweapon type候補、`position`はUI表示位置候補。 |
| gun同一entityの別component | `progress` | `value/min/max` | UI L551–559。gun rowの同一entityにだけ読む。slotのprogressから代入しない。 |
| gun同一entityの別component | `barrelsModifier` | `barrels`（最大少数ID候補）、`mode` | UI L447–449、501–503。barrels各IDは参照候補として記録し、ID先entity progressは別entity候補行として別に取得・同じIDが一致した場合のみ関連表示。 |
| gun同一entityの別component | `serialLoaderModifier` | `serialLoads`（最大少数ID候補） | UI L451–455、501。現`serialLoad` collection 0件では代替できない。各列挙IDに自動推測joinせず、取得scopeとexact ID matchの両方がある場合だけ参照関係として示す。 |
| `reloadBar` collection | `reloadBar` | entity ID candidate; `rowsCount/order/prevOrder/iconName/isOutOfBounds`、兄弟`weapon.type` | UI L89、106–115、169–180。表示行の文脈用。progressは含まれない。 |
| `weapon`（必要なときのみ） | `weapon` | `type/state/groupsCount/canForceReload` | UI L169–183、233–255。weapon type rootの対応とgroup分岐に使用。 |
| grouped時に限る | `groupModifier` / `gunsGroup` | `groupID/reloadBarOrder`; `type/groupID/mostReadyGunId` | UI L262–267、316–319、390–395。非grouped艦では先行取得しない。groupModifier itemsのIDはgun IDsとしてUIが使う。 |
| ID参照先: barrel/serial-load | `progress`、必要時`serialLoad` | progress `value/min/max`; serial `index/weaponType/state` | `barrels[]`/`serialLoads[]`が示したentity IDに対する候補取得。collection全件をslot/gunに無条件joinしない。 |

`GunBarrel`はComponents.xmlでempty component、`ReloadModifier.duration`と`ChargeModifier.duration`はsync=falseで、確認したbar式はこれらをprogress値に使っていない。初版診断では無理にdurationを読む必要はない。`GunsCount`はsync=falseの集計値なので、管progress代替・行生成根拠には含めない。後で必要性を確認してから独立候補にする。

### key、collection、root scope、ID関係

- Collection route名とcomponent keyはUI参照から導いた**候補**。`getEntityCollections('gun'/'reloadBar'...)`が実機dataHubで有効かは別途確認が必要。key未対応とcomponent未取得を区別して記録。
- 根root scopeはbattle reload HUDで使われるdataHub collection。確認したrendererに自艦ID predicateや`selfVehicle` owner joinは現れていない。UI上の戦闘表示が自艦用に構成されることからPython側で全collection行を自艦と決めつけない。
- 各collection行は独立して最大32件の候補取得、固定fieldsのみ。各rowの`entity.id`を`entityIdCandidate`として保存する。
- gun→barrels/serial-loadの関係はgun modifier array内のID。gun entity上のmodifierを読んだうえで、個別ID先のprogressを別root/snapshot内候補として取得する。matchは正確なscalar ID一致だけを表現し、関連の意味は`unverified`のまま。
- grouped gun listは`GroupModifier` collectionのindex path `byWeaponType/byGroup`、代表はcomposite key `(weaponType, groupID)`の`GunsGroup.mostReadyGunId`。この関係はUI根拠だが、Pythonでcollection同士を結合する場合はsource/scope/IDを明記し、欠損時にnearest/order/typeだけで推測joinしない。
- slot↔gun、slot↔barrel、slot↔serial-loadのID relationは確認できていない。type equalityや「Undineの魚雷は1種類」等で結びつけない。

### 上限・欠測・異常時

- collectionごと最大32 entity、配列（barrels/serialLoads）は最大16 ID、文字列128 chars、有限数のみ、container深さ3／総budget64を既存safe candidate copierと同じ上限にする。ID配列は固定長とし任意objectをstring化しない。
- `unsupported`=getter/key/component key不在、`unknown`=例外/None/field読出不能、正常な空enumeration=`available`かつ0 rows、enumeration途中例外=`partial`、32超過=`truncated`。これらを0、false、空配列に埋めない。component-level statusとfield-level statusを区別する。
- `Progress.max == 0`、欠落、非有限値、負値はraw field/statusのまま記録し、割合／残時間を算出しない。診断初版では`value/max` rawだけ。UI式の`max-value`、`value`を用いる条件分岐は別項目として実機で検証するまで採用しない。
- gun rowsが32超過、group relationship不明、modifier ID不在、別component unavailableの場合、見えた行だけを記録し「全管」扱いにしない。正常な空gun/serialLoad collectionも対応UIに管が無い根拠にはしない。
- 個人IDは文書に転記しない。通常の記録本文には実IDを載せないが、診断出力では関係照合のためboundedな実entity ID候補を出してよい。試験報告・公開docには転記せず、record-local pseudonymを使う。

## 次の実装案と最小試験

### 実装（診断だけ）

1. `weapon_hub_probe`を維持し、別bounded helper `gun_reload_probe`を`torpedo_telemetry.py`に実装。
2. `gun`/`reloadBar`/`gunBarrel`各collectionを最大32、modifier IDは各16、`getEntity`での解決は合計16まで。getter/key/field status、partial/truncated、有限scalar、source、semantics=`unverified`を出す。
3. `Main._build_state`にsafe境界で`gunReloadProbe`を追加。slot relationやorder/type推測join、履歴、残秒等の派生、通常stateへの補完はしない。
4. 実機取得可能性・意味は未検証。次の単発試験は[0.3.8短試験手順](TEST_GUN_RELOAD_0.3.8.ja.md)に限定する。

### 最小試験の判定点

- 静止状態でUIに見えるgun/barrel bar数とdiagnostic rows/ID参照が対応するか。grouped/serial loaderがなければ、まずgun単位progressのみを照合。
- 発射直前→発射直後→7:15完了表示の間で、slot progressとgun/barrel progressのどちらが変化するか。各raw state/value/maxと画面を同一時刻帯で照合。
- `serialLoad` collection 0 rowsでも、gun `serialLoaderModifier`有無・`serialLoads` ID候補・ID先entity取得状態がどうなるかを独立記録。空collectionだけでserial loader非搭載とは判定しない。
- 1条件の成功を一般化せず、取得不能なら「probe coverage不足」、取得可能だが値不変なら「当該経路で変化未観測」、UIとも対応した場合に限り「その条件で対応確認」と分ける。

初版実装・オフラインテスト済み。ゲーム上の取得可否・意味は未検証で、実機試験は未実施。
