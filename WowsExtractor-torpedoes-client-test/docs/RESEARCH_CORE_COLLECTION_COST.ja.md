# core collection 0.1秒経路の静的コール数調査

## 範囲と前提

- 対象正本: `WowsExtractor-torpedoes-client-test/`、HEAD `4224a33f93c74794a7b93bd9396b2c897b6260e2`（0.3.17）。本書はソース読み取り調査で、機能追加・ゲーム実行・attach・負荷生成はしていない。
- 現状: 0.3.17 source-only。collection/diagnostics は既定OFF、diagnostics は有効時1Hz、diagnostic sample 内の同名 collection getter 共有済み。288 pass / 1 skip は既存の基準報告であり、本調査で再実行した結果ではない。実ゲームmodは退避済み。
- 通常収集の概算は 24 ship (`getAllShips()` が24要素)、1回のstate buildを前提とする。件数はコード上の呼出し上限・分岐上限であって、WoWS API内部コストや所要時間ではない。None/例外/属性不在時には同じ項目の値取得を試みるfallbackが追加されるが、鮮度が同じとは限らない。
- `_tick()` はperTick callbackから呼ばれるが、state build/writeは `_stateInterval` により約0.1秒間隔へthrottleされる。tick開始時の `now` をsnapshotの `ts` に使い、以降のgetterが原子的に同時刻の状態を返す保証はコード上ない。

## 呼出し数の見積り

| 経路 / 位置 | 1 stateあたりのAPI呼出し見積り (24艦) | 根拠・条件 |
|---|---:|---|
| `Main._build_ships` `Main.py:1741-1760` | `battle.getAllShips()` **1**、`battle.getPlayerByVehicleId(vehId)` **0–24**（有効vehicle IDごとに1）、その後の位置fallbackで同API **0–24**。したがって合計 **最大48**。 | 1巡目で各艦のplayer解決。`_get_ship_position` はship上で座標が取れず `vehId` があれば再lookupする。 |
| `Main._get_ship_position` / `_position_from_obj` `Main.py:1499-1579` | 位置がship objectに無い場合、player IDがあれば `getPlayerShipInfo(pid)` と `getPlayerInfo(pid)` を順に最大 **2/艦**。二度目のvehicle lookupが別pidを返す場合、同じ2 APIをさらに最大 **2/艦**。上限は **96 info getter calls**（4×24）。 | 各getterの結果で座標が見つかれば後続は短絡する。ship/player objectの `_position_from_obj` は `getPosition`, `position`, `worldPosition`, `positionHull` の最大4属性を順に試行し、その後 `shipGameData`、mappingを調べる。位置欠落時は最大5 object/艦を検査しうる（属性試行最大20/艦、480回）。これは属性アクセス試行数で、全てがengine API呼出しとは限らない。 |
| `_remember_roster_vehicles` `Main.py:968-994` | `battle.getPlayersInfo()` **1**、None時 `getPlayers()` **+1**。`dataHub.getEntityCollections('avatar')` **1**。 | 全rosterのplayer→vehicle cacheを毎state更新。avatar entityを全件走査する。battle開始時の `_start_collection()` にも1回追加。 |
| `_collect_avatar_health` `Main.py:1464-1469` | `getEntityCollections('avatar')` **1**。 | `index_avatar_health` が返却entity群をhealth component index化。 |
| `_collect_map_positions` `Main.py:1581-1687` (`_build_ships`内) | `getEntityCollections('avatar')` **1**。 | mapPositionと通常時のvisibility収集を同じentity群から行う。diagnostic dueでもこの呼出しは別経路。 |
| avatar collection 合計 | **3回/state**、各々全entity走査。 | roster / health / map positions はそれぞれ独立してgetterを呼ぶ。0.3.17のshared diagnostic snapshotはdiagnostics側のhub collection取得を共有するもので、この3つのcore取得は共有しない。 |
| `_build_self` `Main.py:1471-1497` | `getSelfPlayerInfo()` **1**、`getSelfPlayerShip()` **1**、None時 `getObserverShip()` **+1**、`isObserverMode()` **1**。 | self infoの`shipGameData`各fieldを最大6項目読む。ship位置はgetPositionを1回。 |
| `_self_team` `Main.py:1113-1123` | snapshot内初回のみ `getSelfPlayer()` **1**。失敗時 `getSelfPlayerInfo()` **+1**。 | frame内memoized。`_build_ships` relationとtorpedo relationが同じ値を利用。成功経路ならself player infoの追加取得なし。 |
| `TorpedoTelemetry.torpedoes` `torpedo_telemetry.py:2237-2267` | `getAllTorpedoes()` **1** + `getTorpedoOwnerById(ownerId)` **0–U**（U=一覧中のdistinct non-null ownerId数）。 | 各魚雷rowで固定field群とpositionを読む。owner lookupは同一呼出し内でIDごとにmemoize。魚雷本数に上限はここから導けない。 |
| `TorpedoTelemetry.armament` `torpedo_telemetry.py:2269-2301` | `getSelfPlayerShip()` **1**、そのshipの`getTorpedoesModulesState()` **1**、`getSelectedAmmoId(TORPEDO)` **0–1**、ammo ID取得成功時 `getAmmoParams(id)` **0–1**。 | moduleは全件をfield抽出。`public_data(raw)` は最大depth 6、ただしobjectでは `dir()` の全public fieldを列挙し、再帰する。field数はコード上固定上限なし。 |
| `TorpedoTelemetry.systems` `torpedo_telemetry.py:2207-2235` | `getSelfPlayerShip()` **1** + ship getter **4** (`getConsumablesState`, radar, hydro acoustic, submarine locator)。 | 各返却list/objectのfield抽出。armamentとship取得を共有していない。 |
| `BallisticsTracker` `Main.py:626-729` | per-state `snapshot()`中、 ammoありなら`getSelfHoopRanging()` **1**。`getSelectedAmmoId(ARTILLERY)` はbattle start時/weapon-change event時、`getAmmoParams(id)` はammo ID変更時で、core stateごとの呼出しではない。 | `snapshot()` はcache済みammo fieldを読み、impact speed/penetrationを計算。`getAmmoParams` を毎frame呼ぶ実装ではない。 |

### self/info取得と鮮度について

- 通常成功経路では `getSelfPlayerInfo()` は `_build_self` の1回/state。加えて `_self_team` が `getSelfPlayer()` に失敗したときのみ `getSelfPlayerInfo()` fallbackが最大1回増える。ゲーム開始処理 `Main.py:837-838` にもself info取得があるが、毎stateではない。
- self shipは `_build_self`、`armament()`、`systems()` が別々に最大3回/state取得する。異なる時点・異なるwrapperになりうるため「同じship object」とは仮定できない。
- `_build_state` 内の順序は roster→health→ships/map positions→torpedoes→診断（due時）→self→armament/systems/ballistics。従って同一snapshot内でも先に読んだship/healthと後のself/weaponには処理順の時間差がある。差の実時間・サーバー更新境界はソースだけからは特定できず、`ts=now` は全fieldの取得時刻ではない。

## 重複取得と優先度

1. **avatar collection 3回/state（最優先候補）**: roster vehicle、health、map positionの3走査は同じ `dataHub.getEntityCollections('avatar')` に対する同tick取得。既存成功API doublesで「同じtick中に一度だけ取得し、3用途へ同じentity snapshotを渡す」offline検証を行えばよい。API呼出し数を3→1へできる可能性が高い。entity群がlive mutable collectionで、参照を保持している間に更新されうるかはAPI仕様未確認。コピー/再利用の意味が同じか、成功/None/例外を用途ごとに正しく保つか検証が必要。
2. **self shipを最大3回/state**: `_build_self`、armament、systems間の同一tick再取得。返却objectと取得時点が同じと保証できるAPIなら同一snapshotへの受け渡しで削減できるが、鮮度・例外fallback・observer動作の同値性をdoublesで検証する必要がある。現在は各consumerが別々にlookupしているため、共有を安全とみなす根拠はまだない。
3. **ship位置の連鎖fallback**: 24艦で位置が取れない場合、vehicle lookupの再試行と最大96 player info getterが上限要因。単なる同一snapshotの共有とは異なり、player API結果cacheの有効性・更新時刻・ID再利用を確認する必要がある。別位置APIの試行順/鮮度を変える最適化はこの段階で行わない。

## 次の最小実装候補（2案）

### A. 同一tick avatar collection snapshotの共有（先行候補、鮮度周期は変えない）

`_build_state`内で1回取得したavatar entity群をroster/health/map-positionの3用途へ明示的に渡す。失敗結果の扱い（各用途の空/unknown契約）、遅延評価、entity iterableを複数回走査できる形、rosterの記録タイミングを維持すること。これは新しいcache TTLや1Hz化ではなく、同じstate build内の同一collection取得だけを共有する案。変更前に既存API doublesで各用途の既存出力一致、API呼出し1回、None/例外/empty/list generatorをoffline検証する。

### B. self ship lookupの同一tick共有（Aの後、要契約確認）

一度取得したself shipを`_build_self` / `armament` / `systems`に渡す案。鮮度周期そのものは変えないが、lookupが各consumerの実行時点で返す現在値から、state build前半で保持したobjectへ変わるため、実質的な観測時刻は変わりうる。APIが同一battle snapshotを返す保証、observer fallback、getter例外時の振舞いを確認できるまで実装しない。鮮度保証が取れない場合は三者共有をせず、getter頻度を落とす場合は別途更新頻度変更として扱う。

**現時点で選ばない案:** ship/player position/API結果のtick cache、health/map/rosterの別々の周期化、self ship / armament / systemsを1Hz等へ間引く案。いずれも取得間隔・値の鮮度を変えるか、ID/状態変化の反映を遅らせるため、同一snapshot再利用だけの最小変更とは別扱い。必要性と許容鮮度を先に決める。

## offline検証と所要時間計測の設計

- まず成功API doublesにcall countersを付け、24 ship / 全ship座標あり・欠落・self・dead/empty相当のfixtureを実行する。確認項目: `getAllShips` 1、avatar collection core 3、`getSelfPlayerInfo`通常1（fallback分岐は別fixture）、self ship最大3、torpedo enumeration 1、distinct owner数分、position fallback上限と短絡、ballistics ammo getterがtickごとに再取得されないこと。これはAPIコール数の検証であり、実ゲームFPSや時間の代理値ではない。
- Python `time` builtin、`time.clock`/monotonic相当の可用性・分解能・安全な使用可否はWoWSの制限sandboxで未確認。利用できない時計で計時した結果を0msや「計測不能=0」として扱わない。
- ゲーム時計/battle timerはゲーム進行時間であり、CPU処理の壁時計所要時間と同じとは限らない。pause/速度/更新粒度/非同期処理を含む可能性があるので、コレクション所要時間計として適切か不明。計測の根拠にできると先に確認できない限り使わない。
- 実時間を測る場合の提供元は、まずsandboxで使用可・単調増加・十分な分解能を確認したprocess monotonic/high-resolution clock。存在しなければ、許可済みoffline harness上でhost monotonic clockを計測する（これはgame runtime時間の代用とは明記しない）。実ゲーム計測が必要なら、ユーザー側で許可された安全な計時源が確認できるまで実施しない。計時source不明・非単調・分解能不足時にwall timeやbattle timerへ黙ってfallbackしない。
- optional diagnostic counterは数秒単位で集約し、API呼出数・fallback回数・時計source/statusをまとめて出す。毎frameの詳細log、個人/戦闘記録の転記は禁止。counter自身の計測負荷を別途考慮し、診断既定OFFを維持する。
- FPS換算は行わない。将来時間計測が成立しても、まず個別collection区間とtick全体の分布を根拠・計時source・サンプル数付きで報告し、時間差からFPS改善を断定しない。

## 次の進行案

機能追加は引き続き停止し、次は案Aだけを既存API doublesでoffline確認するのが最小。出力同値・例外契約・1回呼出しを満たせた場合に限り、docs以外の変更許可を得てから実装する。案Bとposition fallbackはAPIのsnapshot/鮮度契約が不明なため、コード調査またはoffline doublesで共有の妥当性を示すまでは保留する。実ゲーム実行・attach・負荷生成・FPS比較は対象外。
