# 0.3.12 B27 Undine潜水艦probe実機検証

## 範囲・読取方法

正本記録 `WowsExtractor-torpedoes-client-test/recordings/without-atm-b27.jsonl` をPythonの `json` で1行ずつ読み、既存の集計用履歴は作らず逐次確認した。読取前後の `stat` は同一（134,686,197 bytes、mtimeNs `1793581147875232300`）。全2,237行の内訳はmeta 2、state 2,235。2つ目のmetaに続くB27のactive state 2,233件を対象にした。先行sessionのinactive stateと末尾の軽量inactive stateにはprobeがなく、終了形状は正常。metaはmod `0.3.12-collection-compat`、battle type TrainingBattleを確認。個人名・player/entity/battle IDは本記録に転記しない。

出力は [`submarine_telemetry.py`](../res_mods/PnFMods/WowsExtractor/submarine_telemetry.py) の固定allowlist/status規則と [`OUTPUT_SPEC.ja.md`](OUTPUT_SPEC.ja.md) に従って評価した。JSON `ts` と `observedAt` は記録値のまま示す。ユーザー申告のHUD時刻との突合は操作順・経過の照合であり、別時計間のフレーム単位の同期を主張しない。

## 取得状態

`selfSubmarineProbe` はactive 2,233/2,233件で `available`。`selfVehicle` collectionは2,233件すべて `available`, `complete=true`, `count=1`。Submarine/Battery componentもすべてavailable。固定fieldは全件で `fieldStatus=available`、`fieldReason=null`、raw typeも数値/boolとして妥当だった。allowlist内の欠測・unknown・unsupportedはなかった。

| component | 候補 | 観測されたraw値 |
|---|---|---|
| Submarine | `depth` | 0〜30.0。0/intと浮動小数の値をそのまま記録 |
| | `depthIndex` | 0、1、3 |
| | `nearestDepthIndex` | 0、1、2 |
| | `showDepth` | false/true |
| Battery | `value` | 209.714279…〜255 |
| | `currentRate` | 0、-1、0.6 |
| | `burnRate`, `baseSpendRate`, `baseRegenRate` | 0.0、-1、0.6（各々全active frameで一定） |
| | `burnedValue`, `maxCapacity` | 0、255.0（各々全active frameで一定） |
| | `batteryState`, `isPotentiallyBurning` | 0→3→1、false（falseは全active frame） |

`depthRanges`, `depthStatesValues`, `depthValues` はスキーマ上の候補だがこのprobeのallowlist外で未取得（値/statusなし）。画面HUDの数値を別途転記した記録はないため、raw `depth`の単位・基準面・物理的な意味は確定しない。positionのy等による深度補完はしていない。

## 操作メモとの時系列照合

ユーザー申告は「8:00潜水開始、7:30最大深度、7:10浮上、6:42二重ピンガー、異常なし」。JSON上の主要なraw遷移は次のとおり。表の時刻は `ts`（秒）と `observedAt`（UTC）であり、HUD時計そのものではない。

| 操作メモ | 近傍の観測とraw遷移 |
|---|---|
| 8:00 潜水開始 | 00:57:11.806729 / `ts=880.213`: `depth` 0→0.0066895、`showDepth=false→true`。この時点のBattery `value=255`, `currentRate=0`, `batteryState=0`。00:57:15.012 / `ts=883.456`には `depth=3.1351`, `depthIndex=1`, `currentRate=-1`, `batteryState=3`。 |
| 7:30 最大深度 | 00:57:43.703 / `ts=912.156`に `depth=30.0` を初観測（今回の最大raw値）、`depthIndex=3`, `nearestDepthIndex=2`, `showDepth=false`。Battery `value=226.2857`, `currentRate=-1`, `batteryState=3`。最大値は浮上側への変化が記録されるまで継続。 |
| 7:10 浮上 | 開始操作と完全浮上のどちらの時刻かは申告だけから断定しない。ログでは `ts=915.309`に `depth` が30から減少し始める。`ts=923.642`には `showDepth=true`、`ts=928.750`に `depthIndex=0`と`currentRate=0.6`、`batteryState=1`へ変化。`ts=930.858`で `depth=0.0`, `showDepth=false`。したがって浮上側の遷移と0への到達は確認できるが、操作開始時刻を特定の1遷移に固定しない。 |
| 6:42 二重ピンガー | 潜水艦は `depth=0.0`, `depthIndex=0`, `showDepth=false` のまま。Batteryは `value` が回復中で、2-hit相当の時点 `ts=958.393`に `value=227.4571`, `currentRate=0.6`, `batteryState=1`。別probeのwaveHitは `ts=950.177`で1 row / raw `hitCount=1`、`ts=958.393`で同じrow数のままraw `hitCount=2`を観測。申告された二重pingとの順序は整合するが、ID joinやhitCountの一般的意味づけはしない。 |

### Battery値の時系列上の事実

- 潜水開始直前から開始直後は `value=255`。深度上昇中にraw `currentRate=-1`となり、valueは減少。最大raw深度30.0のsampleでは226.2857。
- 浮上側遷移後もvalueはしばらく減少し、`ts=928.750`でraw `currentRate=0.6`に変化。0深度到達時は211.0、その後は増加し、二重ping相当のsampleで227.4571、active記録末尾では250.0。
- これはログ上の生値と並びの記述に限る。`currentRate`の符号・単位・ゲーム内意味、batteryStateのenum意味、value/maxCapacityからの割合・時間換算は断定しない。`burnRate=0`, `burnedValue=0`, `baseSpendRate=-1`, `baseRegenRate=0.6`, `maxCapacity=255.0`, `isPotentiallyBurning=false`もraw観測値である。

## 判断

この実機記録で0.3.12のselfVehicle singleton取得と固定Submarine/Battery field読み取り、および申告操作に沿う深度・Battery raw遷移を確認できた。次の実装判断は、これらを出所・raw型・status付きの診断値として利用可能とし、履歴補完や派生値を加えないこと。深度の単位変換、indexのenum化、rate符号からの潜水/浮上推定、Battery割合・残時間は、別根拠が得られるまで実装しない。`depth`/HUD数値の単位確認を理由に同じ潜水試験を安易に再要求しない。
