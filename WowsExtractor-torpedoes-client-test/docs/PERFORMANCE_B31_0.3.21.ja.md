# B31：0.3.21の12隻確認

2026-11-03。ユーザー報告：minFPS 45で安定、カクつきを感じ始める。負荷拡大を中止し、24隻へ進めない。

## 記録確認

私有JSONLを行単位で解析。版は0.3.21-position-read-budget。metaは2件（roster 2隻の旧情報と12隻の情報）。active stateは447件、inactive 2件。active艦行数は12隻423 state、6隻23 state、10隻1 state。ゲーム時計範囲は約46.34秒。metaの旧情報を別の完了試験と数えない。

profilerは9窓available、438件notSampled、writerModeはsyncEncodeWrite。time.clockのruntime意味とFPS因果は未確定。以下は同時計の記録値で、inclusive区間を加算しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships | 438 | 6.849 | 9.233 |
| avatar | 438 | 1.938 | 2.641 |
| self | 439 | 0.655 | 1.021 |
| armament_systems | 438 | 0.405 | 0.591 |
| torpedoes | 438 | 0.023 | 0.066 |
| snapshot_build_total | 438 | 9.984 | 13.320 |
| submit | 438 | 0.886 | 1.618 |
| state_cycle_total | 438 | 10.893 | 14.400 |

全5,224艦行にmap nx/nyを保持。直接getPosition available 2,682、none 2,542。世界座標あり4,626行には較正由来も含まれ、直接値と同一視しない。全active stateがcoreDirectOnlyで、拡張fallback sampledShipsは0。

## 判断・次工程

- B30のships平均1.303ms・cycle平均3.674msに対し、今回は6.849ms・10.893ms。艦数増加に伴う収集負荷増加を観測したが、異なる試験条件であり厳密な比例則やFPS原因は断定しない。
- 拡張探索を止めても12隻でカクつきが現れた。位置fallback削減だけでは問題解消に至っていない。B28の24隻との比較で改善率を主張しない。
- 次のコード調査対象はships内のplayer lookup、直接位置getter、map/visibility取得、艦属性読取りと行構築。現行profilerはそれらを一括計測しており、個別原因を断定できない。avatarも別対象として残す。
- まず既存記録と静的経路を調べ、必要なら既定OFFの限定的な内訳計測を設計する。取得項目を根拠なく削除したり、更新間隔変更だけで解消と扱ったりしない。追加の実機依頼は今は行わない。
- クライアント起動中を確認したため、導入先は変更していない。終了後にmodを保全退避する。
