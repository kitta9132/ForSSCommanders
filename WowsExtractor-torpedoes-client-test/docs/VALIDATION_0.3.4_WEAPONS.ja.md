# 0.3.4 実機記録：weaponHubProbe／兵装（without-atm-b08）

更新：2026-11-01。対象は正本 `recordings/without-atm-b08.jsonl`（28,285,904 bytes）。Python標準`json`で全行をストリーム解析し、個人名、player/vehicle/UI/entity/ammo ID、ammo文字列は転記しない。weapon候補の実測であり、意味の確定とは区別する。

## 記録同定・取得状態

| 項目 | 観測 |
| --- | --- |
| envelope / records | 2,305行。`kind=meta` 1件、`kind=state` 2,304件。全行JSON parse成功 |
| meta | mod `0.3.4-weapon-diagnostics`、schema 1、API 1.0、TrainingBattle、roster 7隻。build番号はmetaから確認できない |
| state | active 2,303件（ts=148.143–386.262）、最後の行2,305がactive=false終了state。`observedAt`は2026-10-31 18:08:29.050–18:12:27.290 UTC |
| probe | active 2,303件すべて`status=available`、`source=dataHub weapon UI candidates`、`semantics=unverified`。metaと終了stateでは省略 |
| collection | `weaponSlot` / `serialLoad` / `ammo`は各active snapshotでavailable。componentKey/field statuses available、`partial=false`、`truncated=false`。error/unsupportedなし |

metaおよびstateにはID候補が含まれるが、個体・ammo・戦闘IDの具体値は記載しない。`ts`は`getTimeFromGameStart()`由来でUnix時刻ではなく、残時間表示と対応させる同期根拠はこの記録にない。

## 候補値・遷移

- **weaponSlot**：3行/snapshot、計6,909 row。`type`は0/2/5が各2,303行。`state`は1が5,561行、3が1,348行。各行の`active=true`、`selected=false`、`shotCount=-1`で一定。別`CC.progress`の`value/max`は全行取得でき、valueは0–95.951899、maxは0、1、2.816、40、96の候補を観測した。
- 各snapshotのstate集合は`{1}` 1,371件、`{1,3}` 905件、`{3}` 27件。progress値は複数snapshotで変化する。これはraw候補の変化であり、特定操作との因果やstate整数の意味を示さない。
- **serialLoad**：2行/snapshot、計4,606 row。`index` 0/1が各2,303行、`weaponType=5`が4,606行。stateは1が3,439、3が778、5が389。別progress `value/max`は全行available、maxは40、valueは0–40。
- **ammo**：3行/snapshot、計6,909 row。`id/hasSecondaryAmmo/isAutoUsage/squadId` field statusとviewDataの`ammoId/title/description/subheader/iconPath/secondaryIconPath/uniqueFeatures/paramsDescriptor` statusは全行available。`hasSecondaryAmmo=false`、`isAutoUsage=false`。実値はID類・文字列を匿名化するため非掲載。

slotの`progress`はweaponSlot componentの属性ではなく、同じcollection entity上の別`CC.progress` candidate。serialLoadも同様。ammoは独立collectionでslot arrayとのjoinをしていない。候補値の型・単位・意味は`unverified`。

## torpedoArmament・魚雷一覧

- probeを含む2,303 stateすべてで`torpedoArmament`のmodules / selectedAmmo / ammoParams statusはavailable。modulesは各4行、`selectedAmmoId`は整数候補、`ammoParams`はdict。取得成功であり、魚雷選択操作やammoの意味を独立確認したことではない。
- `torpedoes`配列は2,304 stateすべて空。`torpedoStatus`はavailable 2,303件、unknown 1件（終了state）。魚雷行がないため、魚雷row上のowner/isOwn/motionは観測されていない。この範囲からowner namespaceは確定できない。
- ユーザー報告はKREMLINに対する煙幕を使った可視性試験で、魚雷発射は報告されていない。ログのweapon候補遷移を発射と推定しない。

## 判定・次アクション

1. **取得確認**：0.3.4でweaponSlot/progress、serialLoad/progress、ammo、torpedoArmament関連候補がこの記録範囲で取得できる。
2. **意味未確認**：`shotCount=-1`は発射数や残弾の証拠ではない。slot単位、state/weaponTypeのenum適用、progressの単位・意味、slot–ammo–serialLoadの対応、owner namespace、発射との因果はいずれもこのログで確定しない。
3. **追加試験**：このB08記録は発射操作の試験ではない。発射後装填との対応は未検証だが、後続B09でユーザー発射申告のある試験を別記録として解析した。B09結果と現在のcontext不明点は [`VALIDATION_0.3.4_B09_WEAPONS.ja.md`](VALIDATION_0.3.4_B09_WEAPONS.ja.md) を参照。B08の煙幕試験を装填試験として扱わず、同条件の再試験も要求しない。

schema上の候補制限は [`OUTPUT_SPEC.ja.md`](OUTPUT_SPEC.ja.md) L167–176、UI側参照の静的調査は [`P1_CODE_RESEARCH.ja.md`](P1_CODE_RESEARCH.ja.md) L87–93。
