# 0.3.4 実機記録：weaponHubProbe／兵装（without-atm-b09）

更新：2026-11-01。対象は正本 `WowsExtractor-torpedoes-client-test/recordings/without-atm-b09.jsonl`（27,098,231 bytes）。Python標準`json`でJSONLを1行ずつ解析した。全体を文書へ展開していない。個人名、battle/player/vehicle/entity/ammo ID、ammo文字列は記載しない。フレーム番号はファイル行番号で示す。

## 記録同定・完全性

| 項目 | 観測 |
| --- | --- |
| envelope | 全2,383行に`kind` / `observedAt` / `mtimeNs` / `data`。`kind=meta` 2行、`kind=state` 2,381行。JSON parse errorなし |
| meta | 2件ともmod `0.3.4-weapon-diagnostics`、schema 1、API 1.0、TrainingBattle。最初のmetaは7隻の別マップ、次は1隻のOcean訓練戦。非公開ID値は省略 |
| stateの区間 | 行2にactive=falseの前区間末尾（ts=386.262）。state行3および5–2382にactive=true 2,379件（現行metaのts=20,594.148–20,839.772）。行2383がactive=falseの終了形（ts=20,839.789） |
| probe | active 2,379件すべて`status=available`、`source=dataHub weapon UI candidates`、`semantics=unverified`。終了形と別区間末尾の2 stateでは省略 |
| 観測時刻 | active区間の`observedAt`は2026-10-31 23:49:15.014740〜23:53:20.636584 UTC（約245.62秒）。終了stateは23:53:20.797646 |

ファイルは終了stateまで収録され、probeはactive最終stateまで存在するため、このログは終端を含む。冒頭の別区間stateを現行metaの試験イベントとして混ぜない。`ts`はゲーム開始からの値だが、このログ／metaに画面残時間への換算根拠はない。以下の時系列差は同一active区間内の`ts`差（併記のUTCはenvelopeの`observedAt`）であり、8:00等の残時間への換算ではない。

## 兵装候補の取得・遷移

active 2,379 snapshotすべてで`weaponSlot` 3行、`serialLoad` 2行、`ammo` 3行がavailable。collectionの`componentKeyStatus=available`、`partial=false`、`truncated=false`。各rowのcomponent/field statusとslot/serialLoadの別`progress` component・`value/max` statusもavailable。欠落・unsupported/errorは観測していない。

### weaponSlot／別progress

| `fields.type` raw値 | 外部enum照合（該当する場合） | snapshot中のraw候補遷移 |
| ---: | --- | --- |
| 0 | `ARTILLERY` | `state`は最初のprogress更新後3、その後1。progressの通常表示値は`1/1` |
| 2 | `TORPEDO` | `state`は最初のprogress更新後3、行933で1へ変化。別progressは`0.102/96`付近から増加し、行932で`95.983/96`、行933で`1/1` |
| 5 | `DEPTH_CHARGES` | `state`は最初のprogress更新後3、行392で1へ変化。別progressは`0.112/40`付近から増加し、行391で`39.980/40`、行392で`0/0` |

3 slot全行を通じて`active=true`、`selected=false`、`shotCount=-1`のまま変化なし。したがってこの診断では選択状態の遷移も`shotCount`の発射・残弾変化も見えていない。`progress`は`weaponSlot`内属性ではなく、同一entityに属する別`CC.progress`候補として出力されている。ammo配列とはID joinしておらず、row同士の対応も推測していない。

type=2のprogressはactiveログの行5（ts=20,594.250、UTC 23:49:15.117825）に`0.102/96`として初観測され、行932（ts=20,690.131）まで増加、行933（ts=20,690.232、UTC 23:50:51.113846）で`1/1`へ戻る。初観測からこの戻りまでts差は**95.982秒**、envelope UTC差は**約95.996秒**。開始以前の発生時点・その変化を起こした操作はログにないため、ここでは「progress値の増加と表示形の切替」と記し、これを発射または装填完了と確定しない。`shotCount=-1`も残弾0や発射数を意味するとは扱わない。

### serialLoad／ammo

- `serialLoad`は2行、`index`候補0/1、`weaponType=5`で全active snapshotに一定。stateはindex 0が`1→3`（行5）から`1`（行392）、index 1が`1→5`（行5）、`3`（行392）、`1`（行777）へ変化。各行の別progress `value/max`は40を上限候補として遷移する。外部enumで`weaponType=5`は`DEPTH_CHARGES`であり、魚雷候補と誤同定しない。slotや魚雷へのjoin根拠もない。
- `ammo`は独立collectionの3行/snapshotで、候補componentおよびviewDataの限定field statusはすべてavailable。ID、タイトル、説明、params文字列等の値は匿名化のため転記しない。slotまたは魚雷との対応関係は未確認。

## torpedoArmament・魚雷一覧との範囲

- active 2,379件で`torpedoArmament.available=true`、modules / selectedAmmo / ammoParams各statusはavailable。modulesは4行で、4行の`state`候補は記録中すべて0。同一の`selectedAmmoId`候補とdict型`ammoParams`が継続したが、実ID・params内容は掲載しない。選択弾の値が存在することは、報告時刻の選択操作を独立確認したことにはならない。
- `torpedoes`はactive 2,379件中、空1,799件、1行580件。配列が初めて空→1行になるのは行1360（ts=20,734.368、UTC 23:51:35.245799）、1行→空は行1940（ts=20,794.160、UTC 23:52:35.070997）。これはweaponHubProbeとは独立した公開魚雷一覧の出現・消失観測だが、行のowner等の詳細・発射帰属は別担当の解析範囲であり、ユーザーの発射操作との対応は確定しない。

## 発射報告との時系列突合

ユーザーの実機完了報告：「魚雷選択8:00、発射7:40、装填完了6:00」。本試験では自艦から魚雷を単発発射したというユーザー申告を観測根拠として尊重する。これはユーザーが報告した操作の証拠であり、JSON内owner IDや魚雷owner namespace一般を確定するものではない。発射と完了の報告上の差は**100秒**。

- weaponSlot type=2（enum上TORPEDO）のprogress候補は約95.982秒で`95.983/96`から`1/1`へ切り替わった。報告の100秒とは数値上約4秒差で近いが、選択8:00／発射7:40／完了6:00とJSONLフレームの対応点がなく、progress変化の開始はログ内ですでに進行中。よってこれは同じ発射後の再装填を測ったという証拠ではなく、100秒reloadの一致／不一致判定もできない。
- slotの`selected`は全期間false、`shotCount`は全期間-1で一定。slot state変化とprogress切替は観測されるが、これらraw候補だけから発射操作との因果は未確定。別系統の魚雷一覧には出現遷移があるが、ユーザー申告上の自艦発射とのowner対応はこの文書では確定しない。
- 独立した魚雷一覧には空→1行の変化があり、何らかの魚雷オブジェクトが取得可能になったこと自体は記録されている。ただしこれはtype=2のprogress切替（行933、ts=20,690.232）より**44.136秒後**で、選択・発射時刻のアンカーもowner照合もない。したがって一覧出現を報告された発射の証拠と断定できず、ゲーム内操作としての発射遷移は独立確定できない。
- `ts`はログ内時刻に限る。metaにゲーム残時間との同期点がなく、`observedAt`もJSONL収集時刻である。したがって残時間からtsを逆算したり、ログ開始時刻を選択・発射時刻とみなしたりしていない。

## enum根拠と意味の境界

外部抽出資料 `../mino-smoke/research/extracted/gui/data/constants/ships.xml` の`SHIP_WEAPON_TYPES`（L174–193）は`ARTILLERY=0`（L177）、`TORPEDO=2`（L179）、`DEPTH_CHARGES=5`（L182）を定義する。この定義によりslot `fields.type=2`を魚雷種候補、serialLoad `fields.weaponType=5`を爆雷種候補と読める。ただし、資料のenumが該当raw fieldへ適用される範囲を超えてstate整数の名称・progress単位・row対応・発射との因果まで確定しない。

0.3.4のschema/docsでは`weaponHubProbe`はUI由来のread-only候補で、正式なdataHub契約・実機値の意味は`unverified`。`shotCount`を残弾と断定せず、progressを残秒／割合と断定しない。対応説明は [`OUTPUT_SPEC.ja.md`](OUTPUT_SPEC.ja.md) L167–176、slotと別progress・serialLoad UI参照の静的調査は [`P1_CODE_RESEARCH.ja.md`](P1_CODE_RESEARCH.ja.md) L87–93。

## UI参照contextとの静的突合（実装変更なし）

外部抽出資料 `../mino-smoke/research/extracted/gui/unbound2/pc/battle/weapons_panel/slots/slot_renderer.unbound` を、正本現行 `res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py`／`Main.py` と対照した。

- UI `SlotRenderer`は`CC.selfVehicle`のfirst watcherからself vehicle entityを得る（L6–7）。そこから`entity.weaponController`を得る（L8）。slotはウィジェット引数`_id`をキーとして`getPrimaryEntity(CC.weaponSlot, _id)`で個別取得する（L10）。ammoも別の`CC.ammo`から`slot.weaponSlot.id`をキーにprimary entity取得する（L16–19）。
- UIのアクティブ武器表示判定は`controller.selectedWeapon == weaponType`（L62）。これとは別に`slot.weaponSlot.active`（L63）と`slot.weaponSlot.selected`（L64）を読んでいる。したがってJSONのslot `selected=false`はUI上「選択武器でない」と同義ではない。UI進捗式も`slot.progress.value/max`（L93–94）で、同一slot entity上の別progress参照と整合する。
- 現行probeは同じ`dataHub`と`CC`を受け取るが、`getEntityCollections('weaponSlot'/'ammo'/'serialLoad')`を直接列挙し（`torpedo_telemetry.py` L297–319, L372–397）、最大32件を読む。selfVehicle、weaponController、UIの`_id`、`selectedWeapon`を取得／照合せず、順序joinもしない。rowにはentity ID候補とweaponSlot componentの`id`候補を出すが、UIの`_id`とcomponent.idの同一性や、primary lookup対象との一致を検証していない。ammoも独立collectionのままであり、UIが使う`slot.weaponSlot.id`によるjoinは実装していない。呼び出し元は`Main.py` L1228–1231。

**評価**：同じdataHubを参照することは分かるが、UIがselfVehicle/controllerを通じて選ぶ対象とprobeのグローバルcollection rowsが同一対象・同一contextである証拠はない。一方、資料だけでprobeがstale/non-liveだとも断定できない。B09のユーザー申告上は自艦単発発射が起きているのに、probeの全slot `selected=false`、type=2 progressの`1/1`への切替が魚雷一覧の初出より44.136秒前という不一致は、scope/contextまたはraw候補の意味のずれを調べる手掛かりにとどまる。`selected=false`単独から誤contextとは断定せず、この不一致だけでもcontext問題を確定しない。

## 判定・次の最小アクション

1. **実機取得**：現行0.3.4のprobe、全3 collection、component/field、progress候補が本ログで取得できることは確認。終端active=falseのstateではprobe省略も仕様形と整合。
2. **観測されたこと**：魚雷種slot候補（type=2）で別progressが約96秒相当の数値範囲を推移し、その後`1/1`に切り替わる。serialLoadはenum上爆雷種（weaponType=5）の候補で、魚雷として扱えない。
3. **未確認**：UI widgetとcollection rowの同一対象性、context範囲、controller選択値の取得可否、progressの意味／単位、100秒reloadとの一致、`shotCount`の意味、ammo配列のslot対応。ユーザー申告の自艦単発発射はこの一試験の実機報告として尊重するが、魚雷owner namespace一般は未確定。
4. **次の実装判断**：ユーザーに同じ操作を直ちに再試験させない。まず静的にdataHubの公開取得面でselfVehicle→weaponControllerおよび`selectedWeapon`を安全に診断できるか、UI `_id`/primary slot lookupとentity collection間の同一性を確認する。次版診断案はread-onlyで、`selfVehicle`/controllerのstatus、取得できる場合のみ`selectedWeapon` raw候補、対象slotのscope/match status、slot `type/active/selected/state/shotCount`、同一entity progress、ammoのlookup statusを別々に記録する。根拠のないjoinはせず、取得不能・対象不一致を`unknown`等で明示し、UIのcontroller選択判定とslot component `selected`は別値として保持する。診断経路をレビューした後も対応が不明な場合だけ、ユーザーと相談して同期試験を行う。

今回、ソース、ゲーム、配布物、生成物は変更していない。`TASKS.md`にはB08/B09の既存資料リンクと判断概要のみ追記した。
