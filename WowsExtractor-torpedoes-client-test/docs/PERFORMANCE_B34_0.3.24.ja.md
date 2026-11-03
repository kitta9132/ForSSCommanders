# B34：0.3.24 player共有の1対1実機確認

2026-11-03。ユーザー報告：minFPS約80、瞬間的低下は稀にあるが安定、カクつきなし。私有JSONLを行単位で解析。試験後にクライアントを停止し、収集mod13ファイルをhash照合して保全退避した。停止直後のprocess残存中はファイル変更せず、終了確認後に退避。

## 記録

- 版0.3.24-player-read-sharing、meta1件、roster2隻。active151件、inactive終端1件、active範囲約30.54秒。2艦142 state、1艦9 state。
- 更新間隔平均0.20360秒、中央値0.20311秒、最小0.20006秒、最大0.20902秒。5Hz動作を確認。
- 全293艦行にplayerIdとmap nx/nyあり。players sampleStatusは全151 stateでcomplete。**indexHits合計293、vehicleLookups合計0**。カウンターはships内のlookup試行だけを表し、他phase/eventのAPI総数ではない。
- 直接getPosition available151、none142。拡張fallback sampledShips0、weaponHubProbe全activeでdisabled。
- profiler available6窓、notSampled145件。time.clock / basis assumed、syncEncodeWrite。以下は記録時計上の値でCPU使用率やFPSへ換算しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships | 150 | 0.172 | 0.338 |
| avatar | 150 | 0.483 | 0.735 |
| self | 151 | 0.673 | 0.946 |
| armament_systems | 150 | 0.404 | 0.586 |
| torpedoes | 150 | 0.019 | 0.056 |
| snapshot_build_total | 150 | 1.851 | 2.710 |
| submit | 150 | 0.742 | 1.209 |
| state_cycle_total | 150 | 2.615 | 3.960 |

inclusive phaseは合計時間として加算しない。sample-local indexの生成はavatar区間内にあるためships単独だけでなくcycleも確認する。

## 比較・判断

B32（0.3.23・1対1・5Hz）のships平均1.317ms、snapshot2.987ms、cycle3.753msに対し、B34は0.172ms、1.851ms、2.615ms。player共有の実利用と記録時計上の区間短縮を確認できた。別戦闘・描画条件であり、FPS変化の因果や24隻時の効果は未確定。

取得元は同sampleのplayers一覧。過去frameのIDやpositionを使っていない。取得coverageとして全行map/playerIdを確認したが、個々のID意味を独立した正解一覧で再検証したものではない。

次はB33と同じ6対6・5Hz・約30秒でindexHits/個別lookup/取得状態/区間時間とユーザー体感を確認する。1対1の成功条件を繰り返さず、24隻にはまだ進まない。
