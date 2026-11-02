# B23（記録版0.3.11）: WaveHit観測検証／0.3.12追補

## 対象と方法

- 正本記録: [`without-atm-b23.jsonl`](../WowsExtractor-torpedoes-client-test/recordings/without-atm-b23.jsonl)。Pythonの`json`でJSONLを1行ずつ逐次解析した。2626行中、state 2624行、meta 2行。個人名、player/battle ID、entity/target IDは本書に転記しない。
- 確認実装: [`submarine_telemetry.py`](../WowsExtractor-torpedoes-client-test/res_mods/PnFMods/WowsExtractor/submarine_telemetry.py) の`wave_hit_probe` / `_collection`。
- 仕様参照: [`PLAN_SUBMARINE_PROBE.ja.md`](PLAN_SUBMARINE_PROBE.ja.md)、[`OUTPUT_SPEC.ja.md`](../WowsExtractor-torpedoes-client-test/docs/OUTPUT_SPEC.ja.md) 0.3.11節、[`RESEARCH_SUBMARINE_SYSTEMS.ja.md`](../WowsExtractor-torpedoes-client-test/docs/RESEARCH_SUBMARINE_SYSTEMS.ja.md) WaveHit項。
- 本件の範囲はwaveHit候補と記録時計の照合。別担当のdepth/Battery/meta解析は扱わない。

## 実装・一次資料上の境界

`submarine_telemetry.py`は`getEntityCollections('waveHit')`を列挙し、`CC.waveHit` componentから`targetID`, `lifeTime`, `maxLifeTime`, `alertTime`, `hitCount`, `isActive`, `weaponType`のみを有限数値／厳密boolとしてraw候補化する。`entityIdCandidate`は候補値にとどまり、`targetID`とは結合しない。collection取得・列挙失敗時は部分行を捨て、`unknown`を返す。

仕様・研究資料が挙げるGUI `Components.xml`上のWaveHit field定義、およびUIでの表示参照は名称候補の根拠に限る。Pythonでの可用性、各fieldの意味や単位、タイマー基準を確定するものではない。特に`lifeTime`を経過時間・残り時間へ換算したり、差分から開始時刻・失効時刻を推定したりしない。

## 記録のWaveHit結果

2622件のactive stateすべてで、`waveHitProbe`は次の同一結果だった。

| 観測項目 | B23の値・状態 |
|---|---|
| probe status | `unknown` |
| collection getterStatus | `available` |
| `CC.waveHit` componentKeyStatus | `available` |
| collection status / reason | `unknown` / `iterationException` |
| `complete`, `count`, `truncated` | `false`, `null`, `false` |
| `rows`, `partial` | `[]`, `false` |

これは**empty successではない**。正常列挙の空成功なら`available`, `complete=true`, `count=0`となるが、B23は列挙中の例外を示す。`unsupported`でもなく、部分結果を明示する`partial`でもなく、上限超過を示す`truncated`でもない。上限到達前の例外として部分行を破棄した`unknown`である。

行がないため、`targetID`, `lifeTime`, `maxLifeTime`, `alertTime`, `hitCount`, `isActive`, `weaponType`それぞれの値・型・fieldStatusは観測されていない。WaveHit行の出入りやfield遷移も観測不能であり、0行を「pingなし」「対象なし」「状態解消」と読み替えない。`lifeTime`についてraw保持の実績もなく、時刻差、失効、開始時刻は判定しない。

## 時計とユーザー報告の対応

stateの`ts`は約1271.574から1546.120まで進み、active記録内の`gameClockProbe.observations.battleTimerBattleTime` rawは0から275へ進んでいた。10分durationとbattleTimeから算出する`inferredBattleRemaining`は600から325。計算式・単位・意味は記録内でも`unverified`であるため、以下は時計候補上の照合であり、WaveHitの時刻を証明するものではない。

| ユーザー報告時刻 | 対応するraw battleTime帯 | 同snapshotのinferredBattleRemaining | waveHit確認 |
|---|---:|---:|---|
| 8:00 潜水開始 | 約118–122（120秒近傍を含む） | 約482–478（480秒近傍） | 全て`unknown / iterationException`、行なし |
| 6:30 完全浮上 | 約208–212（210秒近傍を含む） | 約392–388（390秒近傍） | 全て`unknown / iterationException`、行なし |
| 6:00 二重状態 | 約238–242（240秒近傍を含む） | 約362–358（360秒近傍） | 全て`unknown / iterationException`、行なし |

記録範囲はこれらの時刻候補を含み、記録間隔もおよそ0.1秒である。一方、列挙失敗のため6:00近傍で`hitCount`が1から2へ変わったか、その遷移時刻がユーザー目視と一致するかは**確認できない**。ユーザーの「クレムリンping」は目視による独立対象報告として記録する。`targetID`がクレムリンを指すとは扱わず、名前・艦IDとのjoinも行わない。

## 0.3.12追補：collection互換性の原因候補

B23 JSONLをPython 3.11で1行ずつ読み、2つ目のmeta以後のactive state 2,622件を逐次集計した。全2,622 frameで、既存`weaponContextProbe.collections.selfVehicle`は`status=available`、完全なsingleton row 1件、`componentStatus=available`だった。同一frameの新規`selfSubmarineProbe`と`waveHitProbe`はそれぞれ`unknown / iterationException`のまま。既存`torpedo_telemetry.py`経路は`for index, entity in enumerate(entities)`で列挙し、新規`submarine_telemetry.py` 0.3.11経路だけが明示的な`iter(entities)`と`next(iterator)`を使用していた。

この同一frame差分は、selfVehicle API getterや戻りcollection全体が一律に失敗した説明より、Python 2互換を含むWoWS sandboxで明示的`iter`/`next`名が未公開だった可能性を支持する。既往のsandbox制限（docs 0.3.1で`AttributeError`も未公開だった事例）と合わせ、0.3.12では明示呼び出しを除去して既存成功パターンへ統一した。offlineでは制限builtinsから`iter`/`next`を削除したfixtureでも列挙成功を確認する。

ただし、0.3.11 JSONLには例外class/stageが保存されておらず、元の`iterationException`の実体は特定できない。これは最有力の原因候補に対する互換修正であり、WoWS上で修正後に取得できるかは未確認。特にwaveHitのraw行や実値はB23で取得されておらず、今回の既存weaponContext比較はselfVehicle列挙経路の根拠に限る。

## 判定と次の扱い

- B23の報告（Undineの潜水・浮上操作、クレムリンへのping、6:00頃の目視二重状態、不具合なし）はユーザー申告として保持する。ログから裏付けられたWaveHit遷移とは区別する。
- この記録だけでは、二重状態と`hitCount=1→2`の一致、特定targetIDとの対応、他条件への一般化のいずれも主張できない。
- 0.3.12でコード修正済み。次の最小確認はUndineで20秒だけstatusを取得し、selfVehicle singletonとwaveHit collectionが成功するかを見ること。取得成功を確認するまでは再潜水/pingを求めない。WaveHitのraw実値・意味は別途未確認であり、取得成功後に別フェーズで判断する。
