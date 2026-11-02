# B28：0.3.20性能記録

## 結論

- ユーザー報告は0.3.20（core ON、診断OFF、profiler ON）の12対12で「minFPS 20にほぼ固定、以前よりカクつきが具体化」。FPS値は独立計測しておらず、記録だけから原因や因果は確定できない。
- 正本 `recordings/without-atm-b28.jsonl` をPythonで1行ずつ解析。meta 1件、active state 213件、inactive終端state 1件。記録範囲は約22.6秒であり、戦闘全体を覆ったとは確認できない。metaの版は`0.3.20-opt-in-profiling`、rosterは24隻（両チーム12隻）。
- stateは終端まで更新され、間隔は中央値約113ms（最小59ms、最大217ms）。active行は合計約6.35MB、1行中央値30,825 bytes（平均29,815、最大32,770）。inactive終端stateは更新停止の例外ではなく、最後に明示された停止状態。JSONL内に例外／traceback payloadは見つからなかった。
- `writerMode=syncEncodeWrite`。submit値はgame-thread上の同期encode/writeを含む区間で、別writer threadの測定ではない。

## profilerの成立性と読み方

- 213 active state中、209件は`status=notSampled` / `clockStatus=available`（5秒窓がまだ出力されていない状態）、4件は`status=available`。unsupportedやclock exceptionではなく、4件に8 phaseのcount/total/maxが出ているため、**profiler出力自体は成立**している。
- 時計は`time.clock`、`basis=assumed`、観測分解能`1.4e-6`秒。分解能は保証値ではなく、対象ゲームruntimeでの時計の意味（elapsed wall timeか等）は未検証。したがって以下は記録された時計値の条件付き集計で、実時間やFPS相当と断定しない。clockが使えない場合の0ms代用は行われていない。
- 4窓のphase集計（ms）：

| phase | count合計 | total合計 | max |
|---|---:|---:|---:|
| `state_cycle_total` | 190 | 6,353.454 | 46.457 |
| `snapshot_build_total` | 191 | 6,190.920 | 45.291 |
| `ships` | 191 | 5,224.150 | 39.952 |
| `avatar` | 191 | 720.023 | 5.273 |
| `self` | 191 | 132.687 | 1.143 |
| `submit` | 191 | 192.328 | 1.738 |
| `armament_systems` | 191 | 81.148 | 0.649 |
| `torpedoes` | 191 | 5.668 | 0.083 |

  これらは4個の約5秒窓に出た値の合算。`state_cycle_total`はbuild/submitを、`snapshot_build_total`は内訳phaseを包含するため、total同士を足して負荷総量とはしない。`diagnostics_due`は出力なし（診断処理を実行した計測なし）。`ships`は記録上最大の内訳だが、同じtickでの他phase最大値との足し算や、ゲームFPSへの因果帰属はできない。

## 状態・診断・負荷対象

- 213 active stateすべてでavatar snapshotは`complete`、count 24。selfは全213件でobserverではなくhealth/maxHealthは記録上9,200/9,200。self撃沈後の比較区間はこの記録にない。
- 出力`ships`は24件のstateが186件、12件が20件、その他が7件（終端inactiveを除く）。avatar snapshotの24件completeとは別に、通常ships配列が初期区間で12件に留まる期間がある。
- 診断probe payloadは主要10 probeすべて213件で`disabled`。一方、`diag`にはcore側の船数・位置読み取り等の集計と`avatarSnapshotStatus`がある。これは診断probeが走った証拠ではない。
- `torpedoArmament`は213件でavailable、`ammoParamsStatus=available`だが、`ammoParams`は毎回空dict。ballisticsは毎回`available=false`（記録されたkeyは`available`のみ）。これらの項目は性能計測値ではなく、取得状態の要約。

## 判断と次のコード修正候補

この記録は0.3.20のopt-in profiler実動作と、該当条件での負荷偏り（記録時計上`ships`が最大）を示すが、報告されたminFPS 20の原因を確定しない。0.3.14の撃沈前後報告（外部recorderなし、撃沈後minFPS 110）とも条件が異なり、数値を直接比較できない。

次のコード修正候補は`Main.py:_build_ships`を対象に、車両ごとのplayer lookup・position取得・visibility/属性読取りの重複を、安全な既存snapshotの共有で減らせるか静的確認し、offline fixtureで出力同値・例外時unknownを守る範囲に限定して最適化すること。未計測のAPI内部時間や不確かなキャッシュを推測で導入しない。時計についてはruntime適合を確認できる根拠がなければ、profiler値を実時間と扱わず、時計選択・status表現を修正候補として分離する。

ユーザーから追加の実機測定は求めない。既報のゲーム停止とmod退避先のhash検証済みバックアップを維持し、再導入しない。他modは未変更。
