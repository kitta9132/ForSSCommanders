# B32：0.3.23・5Hzの1対1確認

2026-11-03。ユーザー報告：minFPS 80～60、体感できるカクつきなし。私有JSONLを行単位で解析した。クライアント停止確認後、収集modの13ファイルをハッシュ照合してロード対象外へ保全退避済み。他modは変更していない。

## 記録の確認

- meta 1件、版0.3.23-avatar-read-sharing、roster 2隻。active state 176件、inactive終端1件。active範囲約35.66秒。
- 更新間隔中央値0.20328秒、平均0.20377秒、最小0.20008秒、最大0.21283秒。設定0.2秒の動作を確認。
- 艦数2が167 state、1が9 state。全343艦行にmap nx/nyあり。直接getPosition available 176、none 167。全stateがcoreDirectOnly、拡張fallback sampledShips 0。weaponHubProbeは全activeでdisabled。
- profiler available 7窓、notSampled 169件。time.clock / basis assumed、writerMode syncEncodeWrite。時計のruntime意味は引き続き未確定。以下は記録時計上の値でありCPU使用率やFPSへ換算しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships | 175 | 1.317 | 2.752 |
| avatar | 175 | 0.461 | 0.743 |
| self | 176 | 0.683 | 1.230 |
| armament_systems | 175 | 0.401 | 0.671 |
| torpedoes | 175 | 0.021 | 0.149 |
| snapshot_build_total | 175 | 2.987 | 4.954 |
| submit | 175 | 0.743 | 1.679 |
| state_cycle_total | 175 | 3.753 | 6.668 |

inclusive phaseを合計時間として加算しない。avatar ID読取りの共有により細部の費用帰属は旧版と異なり得る。

## B30との比較と判断

B30（0.3.21・2隻・約10Hz）はユーザー報告minFPS 70～45、カクつきなし。cycle平均3.674ms、ships平均1.303ms、snapshot平均2.918ms、更新間隔平均約0.10318秒だった。

B32では1回の平均cycle・ships・snapshotはほぼ同等で、単発処理時間の改善を実証したとは言えない。更新間隔はおよそ倍であり、実行頻度の削減と報告FPSの上昇は観測できた。ただし別試験、mod変更は複数、modなし基準なしのため、頻度変更単独の効果や因果は確定しない。24艦fixtureの読取り回数削減を実機ms短縮と同一視しない。

低負荷で新しい共有処理と5Hzの動作・map取得を確認した。次に進む場合はB31と同じ6対6・短時間で、更新間隔、1回の時間、報告FPS・カクつきを比較する。これは1対1成功の再試験ではなく艦数増加時の確認。24隻・通常戦へはまだ進まない。追加試験には再導入が必要で、現在は退避状態。
