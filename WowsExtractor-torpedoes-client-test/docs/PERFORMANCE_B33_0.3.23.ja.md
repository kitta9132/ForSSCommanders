# B33：0.3.23・5Hzの6対6確認

2026-11-03。ユーザー報告：minFPS 45前後、「若干カクつきあるかないか程度」。試験終了後にクライアントを停止し、収集modの13ファイルをhash照合してロード対象外へ退避済み。停止要求直後はprocessが残っていたためファイル変更を中断し、終了確認後に退避した。他modは変更していない。

## 記録

私有JSONLを逐次解析。meta 1件、0.3.23-avatar-read-sharing、roster12隻。active206件、inactive終端1件、active約41.94秒。12艦191 state、6艦10 state、10艦3 state、8艦2 state。

更新間隔平均0.20459秒、中央値0.20383秒、最小0.20007秒、最大0.25698秒。5Hz設定の動作を確認。全2,398艦行にmap nx/nyあり。直接getPosition available1,236、none1,162、拡張fallback sampledShips0。

profiler available8窓、notSampled198件。time.clock / basis assumed、writerMode syncEncodeWrite。以下は記録時計上の値で、CPU使用率・FPSへ換算しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships | 199 | 7.438 | 11.760 |
| avatar | 199 | 2.187 | 2.891 |
| self | 200 | 0.711 | 1.894 |
| armament_systems | 199 | 0.437 | 0.794 |
| torpedoes | 199 | 0.028 | 0.068 |
| snapshot_build_total | 199 | 10.946 | 16.284 |
| submit | 199 | 0.925 | 1.537 |
| state_cycle_total | 199 | 11.898 | 17.171 |

inclusive phaseを合計として加算しない。avatar共有で一部読取りの費用帰属は旧版と異なり得る。

## B31との比較・次工程

B31（0.3.21・6対6・約10Hz）はminFPS45安定・カクつきを感じ始めるとの報告。記録時計のcycle平均10.893ms、ships6.849ms、avatar1.938ms、更新間隔平均約0.10390秒だった。

B33は更新頻度がおよそ半分になった一方、1回のcycle平均11.898ms・ships7.438msで短縮は実証できていない。minFPSも約45で、カクつきの表現には違いがあるが定量測定ではない。異なる戦闘・描画条件なので、コード変更による悪化とも改善とも確定しない。オフラインfixtureの読取り削減を実機時間改善と同一視しない。

性能問題は未解消。24隻への拡大・同条件の即時再試験は行わない。追加実機なしで、毎sampleのplayers一覧と毎艦のgetPlayerByVehicleIdの重複を削減可能か調査する。ID一致・欠測・競合・明示fallback互換を確かめ、必要ならships内部の取得と行構築の限定計測を設計する。1回の長い処理と、実行頻度／総回数を分けて評価する。
