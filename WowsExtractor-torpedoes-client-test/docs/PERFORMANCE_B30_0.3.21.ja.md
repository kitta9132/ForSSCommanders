# B30：0.3.21の1対1確認

2026-11-03。私有JSONLを行単位で解析。ユーザー報告はminFPS 70～45。カクつきの有無は未報告。

## 確認できたこと

- metaは2件、いずれも0.3.21-position-read-budget、TrainingBattle、roster 2隻。active state 351件、inactive 2件。activeのゲーム時計範囲は約36.1秒。meta重複を独立した2試験とは数えない。
- profilerは7窓available、344件notSampled。time.clock、basis assumed、観測分解能約1.1μs。時計のruntime意味は引き続き未検証。
- 集計343 sampleの記録値：ships平均1.303ms・最大3.594ms、snapshot_build_total平均2.918ms・最大7.179ms、state_cycle_total平均3.674ms・最大8.337ms、submit平均0.734ms・最大1.873ms。inclusive区間は加算しない。writerModeはsyncEncodeWrite。
- 全683艦行でmap nx/nyを保持。直接getPosition available 351、none 332。拡張fallbackは全683行でnotSampled、sampledShips 0。位置属性の総当たり試行は記録されず、意図したcoreDirectOnly方針で動作した。
- weaponHubProbeとselfSubmarineProbeは全active stateでdisabled。

## 判断と次工程

- 低負荷試験で新しい取得方針と計測出力の実動作を確認できた。ただし、B28は24隻、B30は2隻であり、27.35ms→1.303msをコード変更単独の改善率とは扱えない。1隻当たりへの換算でも固定費・可視状況を除去できない。
- minFPS 45～70を「解消」とは判定しない。同条件のmodなし基準、直接FPS計測、カクつき報告は未取得。profilerの約3.7msからFPSへの因果や残負荷を推定しない。
- 追加の12対12試験や機能試験へ進めない。クライアント終了後に収集modを保全退避する。終了前にはロード対象の変更を行わない。
