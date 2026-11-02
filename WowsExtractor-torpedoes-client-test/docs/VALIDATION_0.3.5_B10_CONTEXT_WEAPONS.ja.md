# 0.3.5 実機記録：context／clock候補／兵装（without-atm-b10）

> **0.3.6訂正：key欠落の意味** — 下記の旧probeが`CC.selfVehicle`/`CC.timer`を`unsupported`と出したのは、実行時の`CC`属性lookupが値を返さず、後続getterを呼ばなかったという観測である。Components.xmlにはSelfVehicle (1526)、Timer (2532)等の定義があり、これだけでruntimeのcomponent key不存在とは結論できない。旧出力にはkey lookup状態とgetter状態を区別する情報が足りず、B10の「component keyを利用できず」という記述は断定を訂正する。battleTimerのunknownもgetter/component/field段階を区別できない。以下の記録値自体は0.3.5 JSONLの事実として維持する。

対象は正本 `recordings/without-atm-b10.jsonl`（31,153,469 bytes）。Python標準`json`でJSONLを逐次読みし、全体をメモリへ読み込まず集計した。個人名・player/battle/entity/ammo等の実ID・ID文字列は記載しない。ファイル行番号は1始まり。

## 記録の同定と範囲

| 項目 | 観測 |
| --- | --- |
| 行数・JSON | meta 1行、state 2,357行。parse errorなし |
| 版 | metaのmod version `0.3.5-context-clock-diagnostics`、schema 1、apiVersion 1.0 |
| 戦闘 | TrainingBattle。metaはOcean、艦種は巡洋艦。具体的なplayer名・IDは省略 |
| active | state行2–2,357相当の2,356 stateが`active=true`。最終state（行2,358）は`active=false` |
| 収録時刻 | active区間のenvelope `observedAt`: 2026-11-01 00:29:48.975694–00:33:52.218868 UTC（約243.24秒）。終了stateは00:33:52.377806 UTC |
| `ts` | active先頭127.534、末尾370.788。これは`getTimeFromGameStart()`由来の記録値であり、画面の残り時間に換算しない |

終了stateではcontext／clock／weaponHub probeは省略され、active stateでは各probeが継続して記録されている。省略を取得失敗とは数えない。

## ユーザー申告の操作時刻

申告された順序は「開始直後10:00に魚雷選択 → 残り8:20で魚雷2本発射 → 残り6:08で装填完了」。発射から完了までは **132秒**、選択から発射までは100秒である。これは画面時刻に関するユーザー報告として記録する。ログには操作イベントや画面時計の同期点がないため、これらの時刻を特定のJSONL行／`ts`へ割り当てない。

## context取得結果

2,356 active stateで同じ結果。`weaponContextProbe.status=unknown`だが、入口の個別statusは次の通り。

| 候補 | status | source／raw |
| --- | --- | --- |
| selfVehicle | `unsupported` | `dataHub.getFirstWatcher(CC.selfVehicle)`。`CC.selfVehicle` component keyを利用できず、watcher取得へ進んでいない |
| selfVehicle entity | `unknown` | sourceはselfVehicle watcherの`entity`。watcherがないため未評価 |
| weaponController | `unknown` | source `selfVehicle.weaponController`。entityがないため未評価 |
| `selectedWeapon` / `activeIdWeapon` | 出力なし | controllerが未取得。値を読めた／選択武器が分かったとは言えない |
| slotContext | `unavailable` | `UI SlotRenderer _id / CC.weaponSlot`。probeはUI widgetの`_id`を得ず、slot collection rowとのjoinも行わない |

したがってcontroller fieldの読み出しに至っていないことは分かるが、原因をruntimeの`CC.selfVehicle` key不在とは特定できない。旧probe上の属性lookupがunsupportedだったという範囲に留める。エラー／probe例外の報告ではない。`weaponHubProbe`がavailableなのは独立したcollection列挙の成功で、selfVehicle/controller context取得の成功を意味しない。

## gameClockProbe取得結果

2,356 active stateすべてでoverall `unknown`、raw時計値なし。各候補は一定で、遷移もなかった。

| 候補 | status | source／raw | 読めなかった段階 |
| --- | --- | --- | --- |
| `timer.currentTime` | `unsupported` | `dataHub.getSingleComponent(CC.timer).currentTime`、raw null | `CC.timer` component keyなし（候補側のstatusがunsupported） |
| `timer.currentServerTime` | `unsupported` | `dataHub.getSingleComponent(CC.timer).currentServerTime`、raw null | 同上 |
| `battleTimer.battleTime` | `unknown` | `dataHub.getSingleEntity(CC.battleTimer).battleTimer.battleTime`、raw null | `CC.battleTimer` keyからのentity取得またはcomponent/field読取結果が利用可能にならず、実装上unknownに集約 |
| `battleInfo.duration` | `unknown` | `dataHub.getSingleEntity(CC.battleTimer).battleInfo.duration`、raw null | 0.3.5 probeがbattleTimer entity上だけを読んだ。battleInfo singleton/collection経路の状態は未評価 |
| `battleTimeLeft` | `unknown` | raw null、`inferred=true`、式`battleInfo.duration * 60 - battleTimer.battleTime`、`formulaStatus=unverified`、`sourceUnit=unverified` | 上記raw候補がないため算出値なし |

`CC.timer`のunsupportedと、battleTimer側のunknownは区別する。後者は`getSingleEntity`例外・None・その後のfield不在等をこの出力だけで区別できず、status以上に原因を断定しない。`battleTimeLeft`はUI式候補による派生値であってraw clockではない。このログには式の検証に使えるrawもUI残時間との対応点もない。

## weaponHubProbe／slotの状態遷移

全2,356 active snapshotでprobe overallはavailable。`weaponSlot` 3行、`serialLoad` 2行、`ammo` 3行が各snapshotでavailable、collectionの欠落・partial・truncatedなし。各slot/serialLoadの`fields`および別`progress` componentの`value/max` statusもavailable。これは値の取得成功であり、その意味やUI対象との同一性は別問題。

### weaponSlot（各slotのrow順はcollection順。UI slot IDへのjoinではない）

| row | `type`候補 | `state`遷移 | `active` | component `selected` | `shotCount` | 同一entityの別progress遷移 |
| ---: | ---: | --- | --- | --- | --- | --- |
| 0 | 0 | 1 → 3（行3）→ 1（行30） | 常にtrue | 常にfalse | 常に-1 | 初期1/1 → 行3で約0.102/2.816から増加 → 行30で1/1 |
| 1 | 2 | 1 → 3（行3）→ 1（行933） | 常にtrue | 常にfalse | 常に-1 | 初期1/1 → 行3で約0.102/96から増加 → 行932で95.966/96 → 行933で1/1 |
| 2 | 5 | 1 → 3（行3）→ 1（行390） | 常にtrue | 常にfalse | 常に-1 | 初期1/1 → 行3で約0.111/40から増加 → 行389で39.963/40 → 行390で0/0 |

各slot rowの`type/state/active/selected/shotCount`は全active stateでavailable。`selected=false`はweaponSlot componentの値であり、UIの選択predicateとは別。slot `shotCount=-1`も全区間一定で、発射数／残弾として解釈しない。

row 1（`type=2`候補）のprogressは行3（`ts=127.636`）で増加中の値として初観測され、行932（`ts=223.500`）で95.966/96、行933（`ts=223.603`）で1/1へ切り替わった。初観測から切替までの`ts`差は約**95.967秒**、`observedAt`差も約95.97秒。記録開始時にすでにprogressが進行中だった可能性があり、開始点はログ外。`type=2`のenum対応を適用して魚雷slot候補と呼ぶ場合でも、row自体がUIの選択対象・ユーザーが発射した管と同一である証拠はない。progressの値／最大値はUI表示候補rawで、単位を秒と確定しない。

### serialLoad／ammo collection

- `serialLoad`は2行で、index候補0/1、`weaponType=5`。各行のfield/progressは取得可能。weaponSlotへのjoin根拠はないため、魚雷発射・装填の証拠として使用しない。
- `ammo`は独立collectionで3行。取得statusはavailableだが、weaponSlot rowとのjoinはしない。ID、名称等の個人識別には当たらないゲーム内値も本資料には転記しない。

## torpedoArmamentの既存取得経路

2,356 active stateすべてで`torpedoArmament.available=true`、`modulesStatus`／`selectedAmmoStatus`／`ammoParamsStatus`はavailable。

- `modules`は4要素のlist。各要素は`getTorpedoesModulesState()`から採る`type/currentHP/maxHP/state/critTimer`に`position`を加えたshape（`torpedo_telemetry.py`の`MODULE_FIELDS`／`armament()`）。記録中4要素のtype/state/HP候補は一定（匿名化したtype候補9、state 0、currentHP=maxHP=1800）。これらは管ごとの残数や装填時間ではない。
- `selectedAmmoId`は整数候補で全active区間一定。実値は識別値として非掲載。取得成功や一定値はユーザーの10:00の選択操作を直接確認しない。
- `ammoParams`はdict型でstatus availableだが、全active stateで空dict（0項目）。したがってammo IDの取得とは異なり、性能パラメータ値を得られた実績はない。
- 終了stateはactive=falseでarmament unavailable、modules空・ammo値なし。active時の取得結果と混ぜない。

この経路はbattle APIの`getSelectedAmmoId(TORPEDO)`／`getAmmoParams(id)`と`getTorpedoesModulesState()`であり、weaponHub collectionとは別。`selectedAmmoId`が存在しても、weaponHubのrowやユーザー操作との関連付けは作れない。

## 申告時間とprogressの突合せ・判断

申告は8:20の発射から6:08の装填完了まで**132秒**。対してJSONLでは魚雷slot候補row 1のprogressが記録上約95.967秒で1/1へ切り替わった。数値差は約**36.03秒**であり、同じ132秒を観測した／一致したとは言えない。さらに、操作時刻とstateを結ぶ時計候補はすべてnullまたはunsupported/unknownなので、95.967秒の区間を申告された発射後の再装填と断定する同期根拠もない。

差の説明として残る候補は、progressの記録開始時点ですでに進行していたこと、slot collection rowがUI選択中のslotとは別対象であること、二発射と単一progress遷移の対応が分からないこと、progressの意味・単位が未検証であること。どれか一つを原因と断定しない。`ts`を残時間へ変換して操作時刻を当てはめることもしない。

UI静的参照ではSlotRendererの選択表示predicateは`controller.selectedWeapon == weaponType`で、別途slot componentの`active`と`selected`も読まれる。現行probeは最大32件の`weaponSlot`/`ammo`/`serialLoad` collectionを列挙し、UI `_id`、controller `selectedWeapon`、`getPrimaryEntity(CC.weaponSlot, _id)`によるslot参照を取得・joinしていない。よってslotの`selected=false`を「魚雷を選択していなかった」と読むのは誤り。

## 次のコード側調査（同じ実機操作を直ちに再要求しない）

1. `CC.selfVehicle` keyがunsupportedになる実行環境側のcomponent定義・DataHub公開面と、実際のUI SlotRenderer watcher経路をソース／スクリプト資料で照合する。`weaponController.selectedWeapon`および`activeIdWeapon`の取得には、前段のselfVehicle entityが必要。
2. UIの`_id`がどこから渡され、`getPrimaryEntity(CC.weaponSlot, _id)`がcollection列挙row／component `id`とどう対応するかを静的に追う。根拠なしjoinは実装しない。対応可能なら次のread-only診断でtarget scope・match status・`selectedWeapon`をslot `selected`とは別フィールドとして出す。
3. 0.3.5記録だけではkey/getter/component/field段階は特定できない。0.3.6でこれらを分けて再診断する。取得値やcollection意味は実機確認まで未確定で、ゲームUI式・単位は照合根拠なしに確定しない。
4. weaponHubのprogress値・max値のUI renderer表示への流れ、slot/progress同一entityの対応、操作時にどのrowが変わるかをコード資料で先に調査する。今回の95.967対132秒を検証済みのreload値として扱わず、コード調査でなお不明な点が実機でしか識別不能と分かった場合に限り、追加試験を相談する。

この検証ではゲーム／mod実装を変更していない。成果物は本新規文書のみ。
