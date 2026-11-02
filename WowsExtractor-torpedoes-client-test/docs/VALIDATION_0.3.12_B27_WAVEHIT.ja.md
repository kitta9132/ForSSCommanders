# B27：0.3.12 waveHit実機観測

## 結果

対象記録は[`recordings/without-atm-b27.jsonl`](../recordings/without-atm-b27.jsonl)。ユーザー申告はUndineで「8:00潜水開始、7:30最大深度、7:10浮上、6:42二重ピンガー、異常なし」。本メモはwaveHit専用の観測であり、深度操作の成否・深度値との対応は別担当とする。記録上の対象艦を特定できる結合は行わず、targetIDは値を伏せて`T1`と表記する。

Python標準`json`でJSONLを逐次解析した。2,237行すべて解析成功（meta 2、active state 2,233、inactive state 2、失敗0）。waveHitProbeはactive state 2,233件すべてにあり、line 4〜2236。記録の`ts`は760.6847837884〜996.1071554888。ファイルは変更せず読み取りのみ。

## collection／行遷移

| line | waveHit status / collection | rows | partial / truncated | 読み取り |
|---|---|---:|---|---|
| 4〜1797（1,794 snapshot） | `available / available`、`complete=true` | 0 | false / false | 正常な空collection。probe/列挙失敗ではない |
| 1798〜2236（439 snapshot） | `available / available`、`complete=true` | 1 | false / false | `T1`の行が1件 |
| 全2,233 snapshot | top-level `available` | — | — | unknown、unsupported、partial/truncatedは0件 |

行は1件だけ出現し、記録終了まで残る。追加・削除・行数変化はなく、終端のactive stateでも行は存在する。inactive stateは軽量終端形式でprobeなし。`T1`のtargetID raw値は439行すべて同一だが、値の転記やroster／ship／entityへの推測joinはしない。

## fieldの全遷移

| field | 初出（line 1798） | 変化 | 以後／終了時 |
|---|---|---|---|
| `targetID` | available / int、`T1` | なし | 全439行available、同一raw値 |
| `lifeTime` | available / float、24.9913470997 | **各snapshotで更新**。初出後は減少し、line 1876で49.9398380993へ上向きに更新、その後ふたたび減少 | 変更前の最終値16.8836727892（line 1875）、更新後は49.9398380993→12.2101415126（line 2236）。更新後も減少中に記録終了し、0・消失・失効は観測せず |
| `maxLifeTime` | available / float、25.0 | line 1876で25.0→50.0 | 50.0（残り361行） |
| `alertTime` | available / float、8.3 | なし | 8.3（439/439） |
| `hitCount` | available / int、1 | line 1876で1→2 | 2（残り361行） |
| `isActive` | available / bool、true | なし | true（439/439、型もbool） |
| `weaponType` | available / int、6 | なし | 6（439/439） |

全7 fieldは全rowで`fieldStatus=available`、`fieldReason=null`。別型・unknown・欠落・非bool値は観測しない。最初のrowでは7 fieldすべてavailable。

`lifeTime`は名前だけから残り時間やendTimeとは解釈しない。観測値はline 1798〜1875で24.9913470997→16.8836727892、line 1876〜2236で49.9398380993→12.2101415126。両区間とも各snapshotで更新し、sample間隔は概ね0.10〜0.12秒、中央値の変化率は約−1.01 raw単位/秒。line 1876の値の上向き更新は`maxLifeTime`と`hitCount`も同時更新したrefresh候補。観測終了までrowが残り、失効タイミング自体は未取得。

## first1／first2と6:42照合

ゲーム時計候補`battleTimerBattleTime`と式からの`inferredBattleRemaining`は、該当snapshotでともにavailable。ただし記録自身がunit・意味・式をunverifiedとしているので、以下はraw値と残り時間候補の照合である（duration raw 10.0、式候補`10*60-battleTime`）。

| 観測 | line / `ts` | raw battleTime | inferred remaining候補 | rowの変化 |
|---|---|---:|---:|---|
| first1（初の1件） | 1798 / 950.1772505911 | 190 | 410秒＝6:50候補 | `hitCount=1`, `maxLifeTime=25.0`, `lifeTime=24.9913470997` |
| first2（2件目のpingを示唆する更新） | 1876 / 958.3927696021 | 198 | 402秒＝**6:42候補** | 同じrowで`hitCount` 1→2、`maxLifeTime` 25→50、`lifeTime` 16.8836727892→49.9398380993 |

first2の時刻候補はユーザー申告の6:42と一致する。申告の「二重ピンガー」と同時刻にhitCountが2へ増えたことは当該操作に対応する有力な確認材料。ただしraw clockの意味が未検証であり、probe単独ではpingの操作回数・条件・命中先／命中区画を確定できない。first1は6:50候補で、申告された8:00／7:30／7:10操作とのwaveHit上の対応を示す遷移はない。

## 判定と次の具体的な確認

- waveHit取得経路はこの記録で正常稼働。最初の1,794 snapshotは正常空、続く439 snapshotはrow 1件で、collection失敗やfield欠損ではない。
- 6:42候補のsnapshotで`hitCount=2`となり、同じsnapshotで`maxLifeTime`と`lifeTime`も更新。ユーザー報告の二重ping試験に対応する確認として扱えるが、全条件や命中区画が確定したとはしない。
- 対象艦名／targetIDの対応付け、ping対象・命中区画の推定はしていない。過去戦の艦を今回の対象と同一視していない。
- 同じ実機試験の再要求は不要。次は既存コード／調査で、**匿名化したrowごとにsampleTs・battleTimer raw・全field raw/statusを時系列CSVへ出すスクリプト**を追加し、`lifeTime`の更新／消失を機械的に検出する。また、UI録画が既にある場合だけ6:50候補と6:42候補の画面時計・ping表示をフレーム照合し、時計式と2報告の対応を検証する。新たな実機試験が必要と判明した場合も、対象条件・画面時計・ping回数を同時記録する最小手順を先に提示する。
