# 0.3.7 B12 魚雷・運動・UI・地図較正の確認

対象は `recordings/without-atm-b12.jsonl`。JSONLを1行ずつ読み、全体を一括表示せずに解析した。meta 1行とstate 1,644行を確認。報告されたプレイヤー名・player ID・battle IDおよび実体IDの値は本メモに記載しない。

## 結論

- 「Undineが残り8:00で魚雷1本を発射し、7:15に装填完了」という報告と、観測可能な範囲は時計値で整合する。魚雷初出は残り7:59相当、最後に観測した魚雷行は残り7:15相当だった。時計側の単位・式は未検証のため、秒単位の正確さは主張しない。装填完了そのものの検証は別担当の解析範囲。
- 魚雷は1本だけ確認され、同じ魚雷行が428 state連続で観測された。最初の位置差分はなく、その後の位置から運動を推定できた。最後の観測後は魚雷一覧・UI probeとも空になったが、消失理由や全寿命はこの記録だけでは分からない。
- `uiId`、`shotId`、owner候補などは当該1本について一貫して記録された。ただし値は匿名化し、各フィールドの意味やID namespaceの一般化はしない。`isOwn` は全行nullであり、自艦発射との断定材料にはしない。
- XYZ位置は取得できたが、地図較正は成立せず、魚雷の `mapPosition` は全行null。UIの `isHoming` / `isSpotted` も全行unknown/null。`type=normal` は観測された生値としてのみ記録し、normal/acoustic等の挙動を解釈しない。
- 今回の停止・観測範囲は有効な限定実機根拠であり、欠測や較正未成立を理由に即時の再試験は要求しない。

## 直接観測

### 出現・識別・位置・運動

- 1,644 state中、魚雷一覧とUI probeの両方に同時に1本があったのは428 state。魚雷0本かつUI probe 0行は残り1,216 state。最多同時本数は1本で、観測された魚雷実体は1本。
- 初出はJSONL 1,161行目（`observedAt=2026-11-01T03:30:00.902136Z`）。最後の行は1,588行目（`03:30:45.333988Z`）。その次の1,589行目（`03:30:45.444044Z`）から記録末尾まで、57 state連続で魚雷一覧とUI probeは空。これは観測上の消失であり、命中・寿命終了・その他の原因を特定しない。
- 428行すべてで同じ `uiId` 候補、同じ `shotId`、同じ owner ID候補が記録されている（値は非掲載）。`ownerType=Submarine`、`ownerTeamId=0`、`relation=1` は各行で一定。owner投影の `uiId` / `name` / `playerName` / `subtype` / `isPlayer` は各行null、`isOwn` も428行すべてnull。これらから所有者本人や自艦との関係を補完しない。
- 位置 `position=[X,Y,Z]` は428行すべてに3成分がある。初回は `[-215.589, -0.140, 275.264]`、最終回は `[-2.358, -0.140, 66.531]`。記録範囲内で水平位置差分に沿って移動したことを示す。これはゲーム座標であり、実距離には換算しない。
- `motion` は位置差分による推定値。初回1行は `available=false`、速度/差分時間なし、観測経過0秒。その後427行でavailable。記録された水平速度は約6.12–7.31 `game_world_units_per_second`、最終行の累積観測距離は約298.39ゲーム座標単位、観測経過は約44.42秒。全寿命・射程・命中を示す値ではない。

### UI値・生type

- 魚雷取得statusと `uiTorpedoProbe.status` は観測区間でavailable。各428行でUI行と魚雷行が対応し、`matchStatus=exactUiId`、`uiType=normal`。
- `isHoming` と `isSpotted` は各428行null、各statusはunknown。明示falseではない。producerはunknownで、`ui.mods_DataComponent` というsource表記だけから属性の提供元を特定しない。
- 魚雷行の `type=normal` は428行すべてで観測。生値の記録にとどめ、pingの有無やnormal/acousticのゲーム内意味を推定しない。

### 自艦systems・深度候補

- `self.position` は全観測中不変で、速力0として記録されている。`selfSystems` に深度に相当するキー／候補は見つからなかった。よってこの記録から自艦の潜航深度や深度状態は判定できない。
- `selfSystems.search` ではsubmarine locator項目はavailableだが、radarとhydro-acoustic項目はunknown。これを深度情報や魚雷探知成功とは読み替えない。

### 地図較正

- 魚雷行428行すべてで `mapPosition=null`、`mapPositionStatus=unknown`、source=null。
- `diag.mapCalibration` は通常state 1,643件で `collecting` / `insufficient_samples`、`sampleCount=1`、`fitSampleCount=0`、holdout 0。係数・RMSEはなく、較正成立フレームは0。自艦は記録中停止しており、魚雷のXYZ取得を地図座標較正の成立と混同しない。

## 報告時刻との限定照合

魚雷初出stateの同一snapshotでは `battleInfo.duration=10.0`、`battleTimer.battleTime=121`。記録された未検証式 `duration*60 - battleTime` では残り479秒（7:59相当）となる。魚雷初回 `motion.observedAge=0` でもあり、報告の8:00発射時点付近での初出と整合する。

最後の魚雷行では `battleTimer.battleTime=165`、同じ計算値は435秒（7:15）。報告の装填完了時刻との数値上の整合は示すが、battleTimeの単位・durationの単位・表示丸め・算式の意味は未検証である。また初出から最終観測までは約44.43秒であり、これだけで装填完了イベントや装填状態の遷移を確認したことにはならない。`timer.currentTime` は別の値（初出276.503、最終320.925）で、残り時間とは扱わない。別担当による装填・時計の詳細解析を優先する。

## 次に優先する確認

1. 別担当の装填・clock解析結果と突合し、UI残時間表示と `battleTimer` 候補の対応および装填完了イベントを確定する。
2. 実機記録が自然に得られた場合に、地図較正サンプルが十分な広がりを得たときの魚雷 `mapPosition` を確認する。較正不成立ならunknown/nullを維持する。
3. UI属性やownerの意味は、この1本の値だけから拡張・一般化しない。今回の結果だけを根拠に再試験を要求しない。
