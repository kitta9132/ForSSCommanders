# B31後：収集頻度と負荷削減経路

2026-11-03。対象ソース0.3.21-position-read-budget。調査のみでruntime実装・設定変更・再導入なし。modは退避中。B30/B31私有JSONLは行単位で解析し、個人情報を転記しない。

## 結論と優先順位

**全データを一律10Hzで再取得・構築・同期書込みする必要性は立証されていない。まず頻度を安全に変更可能にし、重い艦系を分離するのが有力。** ただし頻度低下は単発処理の長さを解消せず、観測遅延・短命状態の取り逃がしと交換になる。FPS改善は未確認。

1. 最小変更候補は既存`state_interval=0.2`（5Hz）。全snapshotの一体性を維持し、ゲームオブジェクト／位置のフレーム間cacheを追加せず、取得・行構築・出力の回数をまとめて減らせる。現時点では候補であり、設定変更も実機依頼も行っていない。
2. 次に**艦＋avatar系を5Hz、必要な動的データを別周期**にする設計。魚雷戦の要件上、全体を1Hzに落とす案は第一候補にしない。自艦・魚雷を10Hzに残す案も必要性／魚雷多数時の負荷は未検証。
3. 同時に単発負荷を削減：avatarの複数走査統合、静的ID情報の再取得削減、同snapshotの重複getter・較正diagnostics構築を整理する。頻度低下だけでカクつき解消としない。
4. 書込み／payload削減は次順位。B31の同期submit平均0.886msに対し艦＋avatarは8.787ms。非同期化だけで主要負荷は除けない。

## 実行経路と測定範囲

`callbacks.perTick(_tick)` → `_refresh_meta(now)` → state間隔判定 → `_build_state` → `_write_state`。

- `Main.py:917–921,1071–1129`：毎フレームcallbackは残るが、state getter／構築／state書込みは間隔判定後。`state_interval`は名前と異なり書込みだけでなく収集全体を制御する。
- `Main.py:830`：現状既定0.1秒、最小0.02秒。最大50Hzを許容するが、その実機安全性の根拠はない。今後の設定説明では上限と安全な試験範囲を明示すべき。
- B31の438集計sample：ships平均6.849ms、avatar 1.938ms、cycle 10.893ms。艦＋avatarは同時計のcycle平均比で約80.7%。inclusive phaseを加算しない（shipsとavatarは別区間、cycleはそれらを含む）。
- `self` phaseは主に自艦info/ship取得であり、後続`_build_self`の全費用を表す名前ではない。cycleの残差を特定APIの費用と断定しない。map/visibilityのavatar走査はships側に含まれるため、avatar phaseだけでavatar全費用とは扱わない。走査統合時はphase境界変更と過去値との比較可能性も明記する。
- B31の状態間隔は中央値約0.1030秒、平均約0.1039秒、active447件／約46.34秒。B30は351件／約36.11秒。10Hz設定でも実更新はフレームに量子化される。
- B31の記録時刻から先頭を採用し、前採用時刻から0.2秒以上の行を選ぶと224/447件、0.5秒なら90件、1秒なら45件。これは**既存行の選択数**であり、scheduler実行・取得漏れ・FPS改善のシミュレーションではない。
- time.clockはbasis assumed。数値をCPU使用率・フレーム時間・FPSへ換算しない。

## A：頻度変更で減る経路／残る経路

| 経路 | 全体5Hz化 | 個別周期化の論点 |
|---|---|---|
| self info/ship、self表示 | 回数減少 | 位置・姿勢を遅らせる許容幅は未検証 |
| avatar捕捉・roster ID補完・HP | 回数減少 | 艦系と同時採取し、HP・aliveの時刻不整合を避ける |
| 艦一覧、直接位置、map座標、属性、較正 | 回数減少 | 最大対象。mapだけ更新してworldだけ古い構成を無表示で作らない |
| 魚雷一覧、owner、位置・motion派生 | 回数減少 | 発射初出・消失の観測遅延、sample間だけ存在する魚雷の欠落 |
| 装填module、消耗品・探知状態 | 回数減少 | module進捗／消耗品は動的。静的paramsと一括cacheしない |
| JSON encode・同期write | 回数減少 | 全体snapshot 10Hzを残すなら書込み回数は減らない |
| diagnostics | state dueに制限される | 設定間隔は別だがdue評価はstate内。stateより高頻度には動かない。B31ではOFF |
| perTick入口・メタ確認 | 残る | 下記Bの探索gate見直しが必要 |
| damage／ballisticsイベントhandler | 間隔では減らない | 全snapshotは再構築していない。イベント記録を欠落させない |

周期候補は設計仮説。5Hzの観測間隔は概ね200ms、2Hzなら500msとなり、これは取得源自体の遅延やフレーム遅延を含まない。外部mapでの補間は派生表示であり、取得時点の生値を置き換えない。魚雷motionは`0 < dt <= 1.0`の差分だけを採用するため、1秒超の間隔では速度派生も利用不能となり得る。較正のdrift判定はbatch数基準なので低頻度化に伴い検出実時間も長くなる。

## B：頻度変更以外の具体的な削減箇所

### 1. 毎フレームのbattle ID探索

`Main.py:1088,1222–1238`ではstate間隔判定より前にmeta処理。retry期間中、arena ID未取得なら`_promote_battle_id()`がmetaReady／0.5秒retry gateより先に呼ばれる。`872–891`ではarena/battleInfoと最大7候補属性ずつを探索する。

**案：ID探索も独立retry dueで制限**し、取得済みや期限切れは即return。遅れて現れるIDの昇格とmeta更新は維持する。ゲーム時計が正常に進む場合は初期12秒の負荷候補であり、長時間続くカクつきの原因とは断定しない。時計0固定では期限に到達せず探索継続・state更新停止になり得るので、時計異常時の別扱いも必要。

`_battle_info_component`の候補getter／collection探索、meta未ready時の`_build_meta`→roster／consumables全構築・writeも計測開始前にある。**ID探索だけでなくmeta処理全体がB31のcycle値に含まれない。** state_interval変更では削減できない経路として別gateを設ける。

### 2. avatarの同一sample内走査を統合

`Main.py:1429–1440`ではcollection捕捉1回でも、`_remember_roster_vehicles`、`index_avatar_health`、`_collect_map_positions`が別々に同じentity群を走査する。`Main.py:991–1020`、`ui_health.py:96–117`、`Main.py:1755–1864`でavatar/vehicle/IDを再読する。

**案：1回のsample内でplainなavatar indexを構築**し、ID対応・HP・map座標へ配る。partial/truncated snapshotから不在＝死亡を推定しない。CCキーもsample内で共有可能。跨sampleのentity保持はしない。ここで減るのは走査とcomponent読取りであり、既に1回のcollection getterを再度削減したと数えない。

### 3. rosterと艦player取得

`_remember_roster_vehicles`は毎snapshot `getPlayersInfo`（なければ`getPlayers`）を取得し、さらに艦ごとの`getPlayerByVehicleId`がある（`Main.py:997–1005,1935`）。

**案：同sampleのplayers一覧から厳密なvehicleId→plain playerId/teamId indexを作り、既知対応で艦lookupを省けるか検証。** ID欠測・遅延出現・同名・0・名前空間相違を扱う。既存damage trackerの対応cacheを船の最新状態として無条件流用しない。静的ID対応を別周期にする場合も低頻度再照合・戦闘resetが必要。効果はAPI個別時間未測定につき未確定。

### 4. 直接位置と艦属性／visibility候補

`Main.py:1940,1962–2082`は位置に加えuiId/team/alive/visibility候補/HP/yaw/name/typeを毎回読む。自艦の直接位置も`_build_self:1613`で別読取りがある。

**案：同snapshotの自艦と艦一覧で位置・既に取得した属性の再利用を検討。** observerを自艦と混同せず、ID確定した場合のみ。静的name/typeの低頻度化、候補診断のdue化は出力の取得範囲変更を伴う。存在しないと決め付けずnotSampledを出す。個別getter費用は現在のships phaseでは分離できない。

### 5. 較正diagnosticsの重複構築

`Main.py:1953–1954`は`observe()`の戻り値を捨てて`snapshot()`を再呼出しする。`map_calibration.py:450–484`のobserveはすでにsnapshotを返す。snapshotはsample reservoirのspanも再走査する（486–525）。

**案：同sampleの戻り値をそのまま利用**する。getter回数・観測範囲を変えずに冗長なplain-data生成を減らせる小さな候補。較正観測自体を低頻度にする案とは別であり、後者はdrift検出遅延・sample不足を評価する。

`map_calibration.py:228–260`には各候補を最大256件のreservoirと比較する重複判定もある。ただし一致時には**早期returnする**。DSFFレビューで示された「12隻×256比較がB31の主要因」という仮説は、ソースと記録による検証で支持されなかった。

既存行の直接world位置＋mapPositionRawだけを現行MapCalibrationへ再生し、同じ判定条件で比較回数を数えた結果：B30は351 stateで350比較（平均約1/state）、reservoir1件。B31は447 stateで14,419比較（平均32.26/state、最大45）、候補2,682・重複2,657、reservoir25件。記録側reservoirもB30は1、B31は6～25件。可視性診断OFFの両記録を用いたplain-data再生であり、ゲーム実行時間は測っていない。したがって空間bucket等の大きな変更を優先する根拠はなく、まず戻り値再利用の小さな重複削減と頻度設計を優先する。reservoir満杯・移動時の最悪計算量は別途fixtureで検証可能。

### 6. params／payload／writer

`torpedo_telemetry.py:2272–2307`では動的moduleと、selectedAmmoId→getAmmoParams→`public_data`が同じ関数。`public_data:145–186`は全public属性の再帰列挙を行い得る。

**案：module進捗とammo paramsを分離**し、selected ID変更・期限・戦闘開始でparamsを更新。ammoIdが同じでも補正値不変とは保証しない。静的扱いは確認済みfieldに限定し、raw paramsのunknownを空辞書成功にしない。

B31のcompact JSON（再encode、実write bytesではない）でships値が平均約15.0KB/state、armament約1.0KB、selfSystems約0.7KB。B30ではarmamentは隣接350比較で変化0、B31ではmoduleが441/446変化。selfSystemsは両記録で毎比較変化（B31はconsumables）。**停船だから装填／消耗品も不変、というcache根拠にはならない。** 魚雷は両記録で変化0なので、多数魚雷時の性能・取り逃がしは未検証。

`Main.py:1050–1068`は同期fallbackが実際のB30/B31のwriterMode。非同期writerのlatest-winsは出力backlogを防ぐだけで、submit前のAPI取得・snapshot構築を省かない。Python serializerのGIL競合も残り得る。delta出力はconsumer変更と欠落復旧が必要で、第一工程にはしない。

## イベント利用の限界

登録済みはbattle lifecycle、damage/shell、artillery ammo、weapon type、squadron。通常handler（`Main.py:1022–1047`）はtracker更新のみで全snapshotを呼ばない。確認済みイベントでdamage/ballisticsの変更管理は可能だが、魚雷発射・消失・艦位置・装填をすべてイベント駆動化できる根拠はない。未確認イベント名を追加しない。

## 個別周期化に先立つ出力契約

- まず全体5Hzなら各snapshotは同じ取得周期で、可変値の跨sample再利用不要。
- 複数周期では各群に取得状態と`sampleTs`を持たせる。snapshotの`ts`だけで古い群を新規取得扱いしない。
- 今回未sampleは`notSampled`。未実行のships/torpedoesを「availableな空一覧」で返さない。readerも未sampleを消失と解釈しないことを先に検証する。
- 履歴保持・表示補間は外部appの責務。collectorで可変位置を暗黙cacheしない。静的plain値のcacheもepoch/取得元/最終取得時刻を明示し、game objectを保持しない。
- 同時dueの処理集中を避ける位相分散は候補だが、同sample共有を壊すと逆にgetterが増える。艦＋avatarは一群とし、まず共有を優先する。

## 次の検証（実機依頼ではない）

1. fake clockで50–144回/秒callbackに対し、0.1/0.2/0.5秒設定のbuild/write/getter回数を検証。長いstall後にcatch-up連発しないこと、非finite・逆行・0/None固定・quitを検証。
2. 上記Bの同sample重複削減を24艦fixtureで比較し、API-call budgetとraw出力同値を確認。runtime改善の証明とは分ける。
3. 分離schedulerは未sample/partial/unknown、時刻鮮度、consumerの非消失扱いを先にテスト。別戦闘やobserverで古い値・IDを再使用しない。
4. その後に必要ならships内訳を既定OFF・bounded aggregateで計測する設計。計測器のcall増加と計測対象を明示する。
5. 実機は以上のレビュー後に別途計画。今は24隻再現・追加試験を依頼しない。全体5Hz案の取得損失と負荷効果は未確認であり、採用済みと扱わない。

設定既定値を変更する場合はMain/config.example/INSTALL/OUTPUT_SPEC/現行README/TROUBLESHOOTINGとwriterの0.1秒前提コメントを同期する。過去版の実測資料は当時の条件を保持する。群別化ではselfTeam、mapVisibility、positionDiagnostics、diagnosticsSampleDueの初期化・共有範囲も明示する。
