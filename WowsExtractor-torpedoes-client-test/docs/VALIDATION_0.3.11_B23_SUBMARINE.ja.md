# B23：自艦Submarine／Battery probe実機確認

## 結果

ユーザー報告：Undineで残時間8:00から潜航テストを開始、6:30に完全浮上。その後Kremlinへpingし、6:00時点で二重状態を確認。ユーザー報告では不具合なし。個人名・プレイヤーID・戦闘ID・entity IDは本記録に転記しない。

正本は [`recordings/without-atm-b23.jsonl`](../recordings/without-atm-b23.jsonl)。Pythonで1行ずつJSON解析した。ファイルは154,724,623 bytes、解析前後のsize/mtimeNsは不変。2,626行すべてparse成功（meta 2、state 2,624）。同ファイルには先行するB2と後続のB3が含まれるため、最新caseである2つ目のmetaに対応するB3のみを評価対象とした。B3はmeta 1件・state 2,623件（active 2,622、inactive終端1件）。metaと全stateのschema/apiVersionは1/1.0、meta versionは`0.3.11-submarine-diagnostics`。記録はATMなし、TrainingBattle、Ocean。ゲームbuild番号はこの記録内で確認できず、B23の操作報告から補わない。

現行`submarine_telemetry.py`と`OUTPUT_SPEC.ja.md`の0.3.11節に照合。probeはraw候補のみで、名前・単位・意味は未検証。時計は同snapshot内のcollection観測から出る`inferredBattleRemaining`を使ったが、duration分・battleTime秒を仮定する式候補であり、確定時計としてではない。

## 操作時刻と記録の対応

| 残時間（ユーザー報告） | 対応するJSONL | 解釈 |
|---|---|---|
| 8:00 | line 1136–1145付近。`ts` 1390.607–1391.553、推定残時間480秒 | 潜航テスト開始との報告時刻に対応。ここから6:30までの約90秒を、潜水艦の潜航能力消費時間として混同しない。 |
| 6:30 | 推定残時間390秒付近（line 2000以降） | ユーザー報告では完全浮上。以降は浮上後の操作区間だが、Battery値がunknownのため回復の有無・量は判定できない。 |
| 6:00 | line 2287–2296付近。`ts` 1510.709–1511.657、推定残時間360秒 | ユーザー報告ではKremlin ping後の二重状態。WaveHitの意味・対象joinは本担当範囲外であり、別解析に委ねる。 |

### selfSubmarineProbe：実取得状態

B3の全2,622 active snapshotでtop-level `status=unknown`、collectionは`status=unknown`, `complete=false`, `count=null`, `truncated=false`, `reason=iterationException`, `getterStatus=available`。これは`getEntityCollections('selfVehicle')`呼び出し後の列挙失敗を表し、空collectionや自艦不在を意味しない。singleton確認前に止まるため、entity ID candidateはnullで、`CC.submarine`／`CC.battery` component keyのstatusはこのrecordから判定できない（component keyへの到達なし）。

全active snapshotで両component statusと全field statusが`unknown`、fieldReasonは`iterationException`、fieldTypeおよびraw fieldはnull。値の形はprobeの固定schemaどおり次の候補名だが、この実機記録ではいずれも値を取得していない。

| component | 固定候補field | B3全active snapshot |
|---|---|---|
| Submarine | `depth`, `depthIndex`, `showDepth`, `nearestDepthIndex` | 各2,622/2,622が`unknown` / null |
| Battery | `value`, `burnedValue`, `maxCapacity`, `baseSpendRate`, `baseRegenRate`, `currentRate`, `burnRate`, `batteryState`, `isPotentiallyBurning` | 各2,622/2,622が`unknown` / null |

したがって深度raw値・深度index・真偽候補、Battery残量・上限・rate・stateの実値や遷移はJSONLからは検証できない。潜航と浮上の操作順は独立したユーザー報告として保持するが、raw `depth`の単位が画面のmetre表示と一致したとは結論しない。y座標等で深度を補完しておらず、unknownをfalse/0に置き換えていない。特に8:00→6:30の区間で能力が減った量と、6:30以降の浮上回復量・速度は、probe取得失敗のため区別して定量できない。

## 既存出力・終端・エラーの区別

active 2,622 snapshotすべてで既存`self`は存在。`ships`はsnapshotごとに1/5/7件と変動し、7件のsnapshotが最も多い。少なくともprobeの失敗により既存state全体が失われた形ではない。最終行は`active=false`の軽量終了stateで、`selfSubmarineProbe`／`waveHitProbe`を含まない。これはOUTPUT_SPECに記載された正常な終了時形状と一致し、inactive化・終端JSONは確認できた。

ただし、全active frameでの`iterationException`は**probe collection列挙エラー**として別途記録する。ユーザーの「不具合なし」は尊重し、これをゲームクラッシュや戦闘終了異常と読み替えない。一方で、クライアント/modログは本記録セットに含まれず、ログエラー0件とは判定できない。正常終了の確認もログエラー不在の証明ではない。

## 0.3.12コード追補：既存経路との同一frame比較

B23の2つ目のmetaに属するactive 2,622 frameをPython 3.11で逐次集計したところ、既存`weaponContextProbe.collections.selfVehicle`は全frameで`available`、singleton 1 row、component availableだった。同じframeの0.3.11 `selfSubmarineProbe`と`waveHitProbe`は全て`unknown / iterationException`。既存weaponContext collectorは`for index, entity in enumerate(entities)`であり、新probeは明示`iter`/`next`を使っていたため、sandbox builtin名の可用性差を原因候補として、0.3.12で同じfor/enumerate形式へ変更した。

記録に例外型/stageは残っていないので原因は未確定。修正後のPythonゲーム実行も未確認である。またこの比較で証明されるのはselfVehicle collection経路の差だけで、B23にWaveHit raw行・値があったことを意味しない。

## 次の判断

同じ潜航→浮上→ping操作は依頼しない。0.3.12修正後の取得確認は、Undineで約20秒記録し、まずstatusのみを取る。collection成功が確認できた場合に限り、後続の深度/Battery操作やpingを判断する。深度の単位確定が目的となる場合だけ、raw取得成功後の独立した画面表示との時刻照合が必要。
