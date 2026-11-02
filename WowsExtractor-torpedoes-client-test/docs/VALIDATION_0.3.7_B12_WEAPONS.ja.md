# B12 実機照合：clock・controller・weaponSlot

## 結論

0.3.7の新しい単一row観測は、この記録では連続して取得できた。`battleTimer.battleTime`、10分の`battleInfo.duration`、その式からの残時間は、ユーザー報告の「残り8:00で発射」と時系列上整合する。一方、発射後に同じtype 2 slotが45秒再装填へ入った記録は**ない**。残り7:15時点でslotは既にstate 1／`progress={value:1,max:1}`であり、その45秒前にもstate 3への遷移がない。従って「7:15に再装填完了した」という報告は、このslot記録では裏付けられず、今回のログ上の45秒装填完了は**初回取得中の装填**に対応する。再装填を成功取得したとは扱わない。

**後続のcoverage訂正（0.3.8）**：当時の「実装修正不要、同試験再実施」は不十分だった。B12の取得対象はslot progressで、UIが管別reload barに使うgun/barrel/serial-load entity経路は未取得だったため、発射後tube reloadのcoverage不足である。同じ試験のclock・選択部分を再実施せず、追加診断後に[0.3.8最小試験](TEST_GUN_RELOAD_0.3.8.ja.md)を一度行う。B12の過去ログに新probe値を遡及適用しない。

## 範囲・方法

- 対象：`recordings/without-atm-b12.jsonl`。Pythonでファイルを行ごとに`json.loads`し、1645行すべてを解析（meta 1、state 1644、JSON parse error 0）。
- metaの版：`0.3.7-collection-observations`。state `schema=1`、`apiVersion=1.0`。
- stateの`ts`範囲は156.247–326.824、記録時刻は2026-11-01 03:28:00.665–03:30:51.337 UTC。1643行は`active=true`、最終1行は`active=false`。
- 個人名、player/battle ID、実体entity ID、ammoParams IDは本書に転記しない。type 2 slotのentityは便宜上「slot A」と呼ぶ。これはこの記録内だけの仮名。
- 対象コードは現行`res_mods/PnFMods/WowsExtractor/Main.py`のstate組立てと`torpedo_telemetry.py`のprobe／`armament()`を照合。weaponHub/context/clock probeはread-only UI候補であり、意味や単位を自動確定しない。0.3.7の`observations`は単一の正常なcollection rowからだけ採用され、collection間joinはしない。

## 記録状態・取得品質

| 項目 | 結果 |
|---|---|
| `gameClockProbe`, `weaponContextProbe`, `weaponHubProbe` | 1643 active stateすべて全体status=`available`。最終inactive frameでは軽量形として省略。 |
| `weaponSlot` collection | active 1643/1643でstatus=`available`、2 rows、`partial=false`, `truncated=false`。 |
| `ammo` collection | active 1643/1643でstatus=`available`、2 rows、partial/truncatedなし。 |
| `serialLoad` collection | active 1643/1643でstatus=`available`、0 rows、partial/truncatedなし。空列挙であり、serialLoad搭載の意味までは確定しない。 |
| `torpedoStatus` | active 1643行はavailable、魚雷配列は0本が1216行、1本が428行。inactive最終行はunknown。 |
| `torpedoArmament` | active 1643行でmodules/selectedAmmo/ammoParamsの各statusがavailable、`available=true`。終端は`available=false`の軽量形。 |
| probe内エラー／JSON行エラー | 集計上なし。inactive行はMain.pyの終了時出力形と一致し、通常probeが欠けたことをactive中のprobe失敗とは数えない。 |

`torpedoArmament`は公開ModsAPIの`getTorpedoesModulesState()`、`getSelectedAmmoId(TORPEDO)`、`getAmmoParams()`の状態であり、UI装填slotと同じ情報ではない。`modules[].critTimer`も故障関連タイマーで、装填時間に読み替えない。

## gameClockProbe：raw、派生値、採用経路

採用された観測は`gameClockProbe.observations`。全ての時刻はstateの`ts`と同じsnapshotで記録される。sourceはそれぞれ別のnamed collection route。

| observation / source | 記録値・取得回数 | status・意味 |
|---|---|---|
| `timerCurrentTime` / `dataHub.getEntityCollections("timer").currentTime` | 1643個の異なる値、156.2395–326.7575 | 全1643 active行でavailable。raw直接値。単位・ゲーム内意味はunverified。 |
| `battleTimerBattleTime` / `dataHub.getEntityCollections("battleTimer").battleTime` | 171個の異なる整数、0–171 | 171行でavailable。その他1472行は観測値がunknown（named collectionが成功・非partial/non-truncated・正確に1 rowという採用条件を満たさない場合を含む）。単位はunverified。 |
| `battleInfoDuration` / `dataHub.getEntityCollections("battleInfo").duration` | raw `10.0`（1643行で同値） | available。durationの分単位解釈は未確定。 |
| `inferredBattleRemaining` | 171個の異なる値、600から429まで | 171行でavailable、他1472行はunknown。式`duration*60 - battleTime`で作る派生値。unit欄は`seconds (assumed; unverified)`であり、直接取得秒ではない。 |

したがって、この試験でrawの時計値として採用されたのは上記3つであり、残時間は別枠の推定値である。取得元を取り違えないため、派生値は別singleton経路を混ぜず、別entityのbattleTimer/battleInfo named collectionsの単一rowを同一snapshotで読むコード仕様に従う。別経路の診断候補は以下の通りで、採用値のfallbackにはしていない：`timer.currentTime`/`timer.currentServerTime` singletonはunsupported、`battleTimer.battleTime` singletonとそのentity上の`battleInfo.duration`はunknown、`battleInfo.duration` singletonはunsupported、formula candidate `battleTimeLeft`はunknown。3つのnamed collectionの診断status自体はavailable。これらの候補statusを観測採用statusと混同しない。

`battleTimerBattleTime=0`の行では派生残時間600、120の行では480、171の行では429となった。ユーザー画面の残り時間と同じ単位・表示源だとは一般化しないが、今回の10分設定で「残り8:00」の操作とraw battleTime 120／派生480が時系列上整合する。派生式の分・秒仮定、`timer.currentTime`の単位、候補値の確定的なサーバー時刻性はいずれも未検証。

## controller selected weapon

`weaponContextProbe.observations.controllerSelectedWeapon`は`weaponController` named collectionの唯一rowから採用されたraw値（source `dataHub.getEntityCollections("weaponController").selectedWeapon`）。`controllerActiveIdWeapon`も同collectionの単一row観測（source同collectionの`activeIdWeapon`）。1643 active行でいずれもavailable。

| 記録時刻 UTC | battleTimer raw | controller `selectedWeapon` | `activeIdWeapon` |
|---|---:|---:|---|
| 03:28:00.665 | 0 | 6 | `pinger` |
| 03:28:07.309 | 7 | 2 | `pinger` |
| 以後、active終了まで | 以後7–171 | 2 | `pinger` |

enumの6/2の意味はunverified。UI predicateとの対応をこの行動内容から確定しない。なお`weaponHubProbe.weaponSlot`側のslot Aは全1643 active行で`selected=false`のまま。これは別field・別collectionのraw値で、controllerの`selectedWeapon=2`と同義でも矛盾の証明でもない。slotの`selected=false`をもってcontrollerが魚雷を選択していないとは結論しない。

## weaponSlot type 2：slot Aのraw推移

active中の`weaponSlot` collectionは常に2 rowsで、type 2 rowは毎回1つ。ID対応はrecord-localの仮名slot Aのみで記す。row field statusは記録範囲で全項目available。slot Aでは`active=true`, `selected=false`, `shotCount=-1`が一貫していた。`shotCount=-1`は有効な残数0ではなく未取得／無効候補として扱い、弾数推定に使わない。

| 記録時刻 UTC | `ts` | battleTimer / 派生残時間 | state raw | progress raw (`value/max`) | 解釈上の注意 |
|---|---:|---|---:|---|---|
| 03:28:00.665 | 156.247 | 0 / 600 | 1 | 1/1 | 直後に装填stateへ遷移する直前の最初のsample。 |
| 03:28:00.775 | 156.350 | 0 / 600 | 3 | 0.1023/45 | 初回装填の進捗が記録され始めた。 |
| 03:28:31.621 | 187.205 | およそ31 / およそ569 | 3 | 30.9577/45 | 進捗raw値が約1/秒で増加。 |
| 03:28:45.621 | 201.186 | 45 / 555 | 3 | 44.9390/45 | 45秒満了直前。 |
| 03:28:45.679 | 201.294 | 45 / 555 | 1 | 1/1 | state 3から1へ遷移。初回進捗開始sampleから遷移まで約44.90秒。 |
| 03:30:00.279 | 275.890 | 120 / 480 | 8 | 0.05083/0.1 | 1 sampleだけの短いstate 8。45秒progressなし。 |
| 03:30:00.388 | 275.991 | 120 / 480 | 1 | 1/1 | 次sampleでstate 1へ戻る。 |
| 03:30:44.894–03:30:51.177 | 320.508–326.758 | 165–171 / 435–429 | 1 | 1/1 | 継続してready様のraw値。発射後45秒再装填のstate 3なし。 |

state番号に公式な意味づけはしない。ただしprogressの形は明瞭に分かれる。初回のstate 3区間は`max=45`で`value`が約0.10から44.94へ増加し、約45秒後にstate 1へ移った。従って`value`はelapsed/進捗側のraw値と整合する。一方、仮にUIが`max-value`を残り秒として表示しているなら、残秒候補はこの区間で約44.90から約0.06へ減少する計算であり、raw `value`そのものを残秒と呼んではならない。UI画面との同時記録がないため、この引き算値もコードが出す観測値ではなく未検証の派生候補に留める。

## ユーザー報告との突合・判断

1. **報告：残り8:00で1本発射。** battleTimer raw 120、派生残時間480の区間（03:30:00 UTC直後）にslot Aがstate 8 / progress 0.05083/0.1の1 sampleを取り、その約0.11秒後にstate 1 / 1/1へ復帰した。時刻は報告に整合する。ただしこの短い遷移は45秒の装填進捗を伴わず、API魚雷1本観測とslotイベントをID結合する根拠もないため、「発射に対応したstate変化」と断定はできない。
2. **報告：7:15に装填完了（発射45秒後）。** battleTimer raw 165、派生残時間435となる前後にはslot Aはすでにstate 1 / 1/1。発射時とされるraw 120以降、state 3または`max=45`の遷移は記録されていない。従って「発射後の45秒再装填完了」はこのJSONLでは確認できず、発射から45秒で完了したと説明するのは誤り。
3. **記録にある45秒遷移の分類：初回装填。** 記録開始直後raw battleTime 0からtype 2 slotがstate 1→3、`progress.max=45`で進み、battleTime 45にstate 1へ遷移した。これは報告された残り8:00での発射より前（派生残時間9:15）であり、発射後再装填と取り違えない。

よって、clock観測は本試験の画面報告との限定的な時系列照合に成功したが、装填候補については「初回装填は約45秒進行するraw遷移を取得、発射後再装填は取得／対応確認できず」が結論。再装填に不具合があったとまでは言えない。報告とログの差の原因（操作タイミング、表示上の別管/別状態、当該UI collection候補の非対応など）は、この範囲の記録だけでは特定不能。

## 次に必要なこと

- **コード修正は不要（現時点）**：read-only probeは候補を正直に記録しており、未発生のstate遷移を補完するべきではない。`shotCount=-1`を残数にしたり、`value`を残秒として出したり、slotの`selected=false`をcontroller選択へ投影したりする変更は行わない。
- **必要な追加試験**：発射直前から発射後にわたりゲーム画面録画とJSONLを同時記録し、選択している管・撃った瞬間・各管のUI countdown値・装填完了表示を残す。同一条件でtype 2のslot Aについてstate/progress全変化を照合する。特にraw battleTime 120近辺のstate 8が、実際の発射イベントか別UI状態かを映像で確認する。
- **45秒の進捗の単位・式**：UI画面の進捗値を`value`の増加および`max-value`候補と同じ時刻で照合するまでは、単位秒・残り時間として採用しない。
- **管との対応**：同型の複数slotを個別に発射できるなら、別々に発射して各rowのID仮名とUI管を識別する。現在はtype 2のrowが一つ見えるという範囲に限られ、controllerや他collectionとのjoinはしていない。
