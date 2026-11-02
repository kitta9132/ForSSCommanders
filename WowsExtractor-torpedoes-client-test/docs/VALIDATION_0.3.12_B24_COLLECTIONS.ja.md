# B24：0.3.12 selfSubmarine／WaveHit collection実機確認

## 結果

ユーザー報告は「完了、異常なしB24」。正本は [`recordings/without-atm-b24.jsonl`](../recordings/without-atm-b24.jsonl)。ファイル名と報告に基づきATMなしの試験として扱う。個人名・player/entity/battle IDは本記録に転記しない。

Python標準`json`でJSONLを逐次解析した。208行すべて解析成功（meta 1、state 207、解析失敗0）。解析前後のstatはsize 12,263,196 bytes、mtimeNs 1793570659358665100で不変。metaおよび全stateはschema 1 / apiVersion `1.0`、metaのmod versionは`0.3.12-collection-compat`、battleTypeは`TrainingBattle`、gameModeは`GAMEMODE_AWESOME`。active state 206件、inactive終端state 1件。記録上のgame build番号は確認できない。stateの`ts`は331.5784251378から353.3301146259まで（約21.75秒）。

現行[`submarine_telemetry.py`](../res_mods/PnFMods/WowsExtractor/submarine_telemetry.py)と[`OUTPUT_SPEC.ja.md`](OUTPUT_SPEC.ja.md)の0.3.12節を基準に判定した。候補値の取得成功と意味・単位の検証は別である。

## B23との差・collection取得

B23ではactive 2,622 frameすべてで`selfSubmarineProbe`が`unknown / iterationException`となり、列挙段階で停止した。既存`weaponContextProbe.collections.selfVehicle`は同一frameで完全なsingletonとしてavailableだったが、新probeの失敗原因はログに例外型・段階がなく確定できなかった。

B24ではactive 206/206で次を確認した。

| probe | status | collection | 件数・完了状態 | 判定 |
|---|---|---|---|---|
| `selfSubmarineProbe` | `available` | `available`、getter `available` | selfVehicle 1件、`complete=true`、`truncated=false` | singleton取得成功。Submarine/Battery componentともavailable |
| `waveHitProbe` | `available` | `available`、getter `available` | waveHit 0件、`complete=true`、`truncated=false` | **正常な空collection**。列挙失敗ではない |

従って、B23のiteration failureはB24で再現せず、0.3.12の`for ... in enumerate(...)`経路で両collectionの列挙が実機成功した。これは当該B24記録での確認であり、B23当時の失敗原因を遡って確定するものではない。WaveHitが正常に空だったことは、この試験で候補entityが0件だったという意味に限り、ping状態や命中がなかったとは断定しない。

## 取得できたraw field

以下は全206 active snapshotでの取得値。`available`は型検査を通過したraw候補を意味し、ゲーム上の意味を保証しない。

| component.field | status / raw type | 記録値 |
|---|---|---|
| submarine.`depth` | available / int 62件、float 144件 | int `0`が62件。floatは`0.0`から`0.2926664650440216`。`showDepth=true`の21件ではfloat値`0.0066895196214318275`〜`0.2926664650440216` |
| submarine.`depthIndex` | available / int | `0`（206/206） |
| submarine.`showDepth` | available / bool | `false` 185件、`true` 21件 |
| submarine.`nearestDepthIndex` | available / int | `0`（206/206） |
| battery.`value` | available / int | `255`（206/206） |
| battery.`burnedValue` | available / int | `0`（206/206） |
| battery.`maxCapacity` | available / float | `255.0`（206/206） |
| battery.`baseSpendRate` | available / int | `-1`（206/206） |
| battery.`baseRegenRate` | available / float | `0.6`（206/206） |
| battery.`currentRate` | available / int | `0`（206/206） |
| battery.`burnRate` | available / float | `0.0`（206/206） |
| battery.`batteryState` | available / int | `0`（206/206） |
| battery.`isPotentiallyBurning` | available / bool | `false`（206/206） |

全fieldのstatusはavailable、fieldReasonはnull。`depth`はint/float双方をrawのまま保持し、意味を補正していない。深度の単位や`showDepth`の意味、depth値の振る舞いは別途画面・操作との照合が必要。Batteryのrateの符号・単位・状態enum、255の意味や残量換算も未確定である。静止状態の値だけからrateの意味・単位を確定しない。unknownをfalse/0へ置換していない。

WaveHitは正常空のためrow field自体がない。従って`targetID/lifeTime/maxLifeTime/alertTime/hitCount/isActive/weaponType`は未取得であり、ゼロ・false・pingなしとしては扱わない。

## 同一snapshotの既存診断・終端

- 同じ206 active snapshotの`weaponContextProbe.collections.selfVehicle`は206/206で`available`、getter/call/component key/componentともavailable、row 1件、partial/truncatedなし。row IDや個人識別値は比較・記録していない。B23で既に動作していたselfVehicle経路との同一frame比較において、B24では新probeも成功した。
- 同じsnapshotの`gameClockProbe`は206/206でtop statusおよび`timerCurrentTime`、`battleTimerBattleTime`、`battleInfoDuration`、`inferredBattleRemaining`がavailable。例として同一snapshotで`battleInfoDuration=10.0`、`battleTimerBattleTime=0`、`inferredBattleRemaining=600.0`から終盤の`battleTimerBattleTime=22`、`inferredBattleRemaining=578.0`まで記録された。これは既存診断のraw値と式候補で、単位・意味確定ではない。collection間の行やentityを推測joinしていない。
- inactive終端stateはline 208でprobeを含まない。OUTPUT_SPEC記載の正常な軽量終了形と一致する。

## エラーとユーザー報告

ユーザー報告の「異常なし」はそのまま記録し、collection取得結果とは区別する。B24の2 probe collection failureは0件で、JSONL parse errorも0件。クライアント/modログは提供記録に含まれないため、ログのエラー有無は判定不能であり、「ログエラー0件」とはしていない。正本のstatが解析前後で不変だったため、今回の読取り中に更新中だった兆候はない。

## 次の最小試験

静止状態だけの追加試験は不要。collection取得が成功したため、次はUndineで同じ試験を繰り返さず、最小限の潜航→浮上→ping操作を行う。raw `depth`/`showDepth`/Battery各fieldの遷移を確認し、ping後はWaveHitが空から非空へ変わるかをstatus・row数・各field statusとともに観測する。操作と画面時刻の対応を記録するが、画面表示との照合なしに深度単位やrateの意味を断定しない。WaveHit rowが得られても`targetID`等をentity/ship位置へ推測joinしない。
