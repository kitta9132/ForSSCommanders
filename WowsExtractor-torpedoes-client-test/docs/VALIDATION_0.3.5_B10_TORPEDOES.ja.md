# 0.3.5 B10 魚雷・運動・UI・地図較正の確認

対象は `recordings/without-atm-b10.jsonl`（31,153,469 bytes）。PythonでJSONLを1行ずつ解析した。全2,358行（meta 1、state 2,357）がJSONとして読め、破損行・途中で切れたJSONはなかった。最後は `active=false` の正常な終了状態だが、終端フレームでは魚雷statusはunknown、較正・時計候補の一部フィールドは出力されていない。これは破損や部分行ではなく、終端状態の欠測として扱う。

## 結論

- テスターの「2本発射」という報告と整合し、記録上も異なる `uiId` を持つ魚雷が2本確認できた。2本は約0.95秒差で一覧に現れ、同時観測は最大2本。これはこの戦闘の観測であり、IDや `shotId` のnamespace・一般的な意味を確定するものではない。
- 2本とも3D位置は直接取得された。連続位置差から速度・進行方向・観測経過時間/距離を推定できた。一方、地図座標への較正は成立せず、魚雷の `mapPosition` は全行unknown/null。
- ATMなしの記録では `uiType=normal` は取得されたが、`isHoming` と `isSpotted` は全魚雷行でunknown/null。UI probe自体の取得成功はこれらの値の取得成功を意味しない。UI値の供給元も `producer=unknown`。
- 記録内の時計候補は有効値を得ていない。魚雷初出をユーザー報告の残時間（8:20等）と照合できず、記録の `ts` を残時間や操作時刻へ換算していない。

## 直接確認できた値

### 出現数・識別・所有者候補

- 魚雷一覧の取得statusは2,356 stateでavailable、終端1 stateはunknown。全2,357 state中、魚雷0本が1,769、1本が19、2本が569フレーム。延べ1,157行、異なる `uiId` は2つ。
- 1本目はJSONL 972行目、2本目は981行目に初出。両方が同時に一覧にいた期間は連続569フレーム。記録中の発射順・同時本数の観測は以上のとおりで、ユーザーの2本発射報告を否定する材料はない。
- 各魚雷の `shotId` はそれぞれ一貫して異なる値（各魚雷行578/579回）、両者の `ownerId` は同じ値。値そのものは記載しない。2本についてだけ確認できた対応であり、`shotId` が艦・戦闘をまたぐ一意IDである等の一般化はしない。
- 1,157行すべてで `ownerId` は艦一覧の `vehicleId` と照合できた。一方、魚雷内の `owner` 投影は名前・playerName・uiIdがnull。owner照合はID候補の直接一致に限り、所有者を名前やUI上の艦へ確定したとはしない。
- `relation=1`、`ownerTeamId=0`、`ownerType=Cruiser`、`type=normal` は全行で取得。`isOwn` は全行null。これらの値の意味から、自艦発射か敵艦発射かを追加推定しない。

### 位置・運動（派生値）

- 各魚雷の `position` は3成分で全1,157行に存在。これは記録された直接位置。
- `motion` は位置差分由来の推定値。各魚雷の初回観測は速度なし、その後の1,155行で速度を算出。差分 `dt` は約0.100–0.117秒、水平速度は約5.03–6.05 `game_world_units_per_second`。
- 連続観測区間は1本目が約59.70秒/331.32ゲーム座標単位、2本目が約59.78秒/331.80単位。進行方向は `headingRadians` 約3.113–3.114（+Z基準、+X方向が正の定義）。これは観測区間の移動量であり、魚雷の全寿命・射程・残距離・命中を表さない。ゲーム座標単位を実距離やノットへ換算しない。
- 魚雷の `mapPosition` は1,157行すべてnull、`mapPositionStatus=unknown`、source=null。較正済み地図上の魚雷位置は今回確認できない。

### UI（ATMなし）

- `uiTorpedoProbe.status=available`、`truncated=false`。各行で同一フレームの `matchStatus=exactUiId`、`uiType=normal` を記録。
- `isHoming` と `isSpotted` は各1,157行でnull、対応statusはunknown。これはfalseではなく、値の意味も今回判定できない。source表記は `ui.mods_DataComponent` だがproducerはunknown。ATMなしという記録条件だけから、この属性の一般的な供給元やATMあり時の挙動を断定しない。

### 地図較正

- `diag.mapCalibration.status` は通常の2,356 stateすべてで `collecting`、reasonは `insufficient_samples`。最大 `sampleCount=1` で、係数採用・RMSE等による較正検証には至らなかった。
- よって較正利用可能フレームは0。艦側の座標が記録されていることと、魚雷の地図座標への変換が利用可能であることは別である。

## ユーザー報告・時計候補との照合

ユーザー報告は「開始直後10:00に魚雷選択、8:20に2本発射、6:08に装填完了」。本メモの対象範囲では、2本が記録に現れた事実を報告と整合する観測として扱う。選択・装填完了は魚雷一覧だけからは検証しない。

2,356 stateの `gameClockProbe.status` はunknown。`battleTimer.battleTime` と `battleInfo.duration` はunknown、`battleTimeLeft` もunknown（未検証の計算式を含む）、timerコンポーネント由来の候補はunsupported。したがって8:20との数値照合は不可。ファイルの `ts` は記録された時系列値としてのみ保持し、残時間・戦闘開始からの経過時間・ユーザー操作時刻に読み替えない。

## 次の実装・試験優先

1. 魚雷の位置・速度推定は現状の直接位置と差分値を分けたまま維持し、複数方向に十分移動する戦闘で較正成立後の魚雷 `mapPosition` を確認する。較正不成立時はunknown/nullを維持する。
2. 追加の発射試験で、同時発射・時間差発射・魚雷消失までを記録し、同一戦闘内の `uiId`、`shotId`、`ownerId` の対応を再確認する。複数戦闘でnamespaceを越えた一意性を主張しない。
3. ATMあり/なしを分けてUI probeの取得・一致・値状態を比較する。欠測unknownと明示falseを分離し、producerが確認できるまではATM供給と断定しない。
4. 8:20等のユーザー時刻との比較は、時計候補が実際にavailableとなり、UI残時間との対応を別途検証できた記録で行う。それまでは `ts` 変換や操作時刻の推定を追加しない。
