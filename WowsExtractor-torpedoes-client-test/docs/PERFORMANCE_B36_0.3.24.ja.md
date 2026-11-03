# B36：0.3.24・24人roster訓練戦

2026-11-03。ユーザー報告：最初の数秒はmin10まで低下、その後min50～60・max160～180、平均120を維持。カクつきの有無は今回明示されていない。試験終了後クライアントを停止し、mod13ファイルをhash照合してロード対象外へ退避。process残存中はファイル変更しなかった。

## 記録とcoverage

私有JSONLを逐次解析。meta1件、版0.3.24-player-read-sharing、roster24隻。active401件、inactive終端1件。ゲーム時計範囲146.6956～228.6143（約81.92秒）。更新間隔平均0.20480秒、中央値0.20535秒、最小0.20004秒、最大0.22615秒。

**stateのshipsは最大20隻**（20艦388 state、11艦9、13艦2、16艦1、18艦1）。24人rosterの訓練戦であるが、24隻同時収集の実測ではない。rosterとgetAllShips由来の一覧のcoverageは別であり、差の4隻を撃沈・失探・収集不具合と推定しない。

全7,919艦行にmap nx/ny・playerIdあり。players sampleStatusは全401 stateでcomplete、indexHits合計7,919、ships内vehicleLookups0。直接getPosition available4,411、none3,508。世界座標あり7,543行は較正由来を含み、直接値と混同しない。拡張fallback sampledShips0。

## profiler

available16窓、notSampled385件。time.clock / basis assumed、syncEncodeWrite。記録時計のruntime意味は未確定でCPU使用率・FPSへ換算しない。inclusive区間は加算しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships | 400 | 0.994 | 1.899 |
| avatar | 400 | 3.935 | 5.659 |
| self | 401 | 0.663 | 1.386 |
| armament_systems | 400 | 0.405 | 0.937 |
| torpedoes | 400 | 0.020 | 0.108 |
| snapshot_build_total | 400 | 6.149 | 9.307 |
| submit | 400 | 0.981 | 1.474 |
| state_cycle_total | 400 | 7.153 | 10.469 |

最初のavailable窓はstate ts151.8209で、cycle25 sample・平均6.920ms・最大8.286ms。後続窓のcycle平均は約7.0～7.5ms。記録されたcore区間内には、冒頭min10への低下に対応すると断定できる特大spikeはない。state間隔も描画FPSとは別物である。

## 判断・次工程

- B28のmin約20固定という報告からは状態が変わり、今回のユーザー報告では冒頭後に平均約120へ回復。ただし版・周期・実収集艦数・戦闘条件が異なるため、FPS改善率や完全解消は主張しない。
- player共有は多数艦でも利用されている。一方、開始直後のmin10は未解決の観測であり、正常扱いして打ち切らない。
- 現行cycle計測の前にlifecycle初期化・meta探索／生成／書込み等があり、記録の始まりとユーザーが言う「最初の数秒」を独立に同期できていない。初期処理、ゲーム読み込み・描画、他mod／外部記録の寄与は未確定。
- 追加の実機再現や通常戦は今は依頼しない。既存sourceと記録で開始時の計測範囲を調査し、必要なら明示opt-inの限定初期計測を設計する。魚雷多数時・診断ON・24隻同時stateの負荷は未検証として残す。
