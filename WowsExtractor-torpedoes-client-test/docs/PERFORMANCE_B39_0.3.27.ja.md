# B39：avatar候補IDとAPI一覧外の観測

2026-11-03。ユーザー報告：minFPS60～70、カクつきなし。試験終了後クライアントを停止し、収集mod13ファイルをhash照合してロード対象外へ退避。他mod変更なし。

## 記録確認

私有JSONLを逐次解析。meta2件はいずれも0.3.27-avatar-id-candidates、roster12。active178、inactive2、範囲約36.12秒。重複metaを独立した2試験とは数えない。平均更新間隔0.20409秒、最小0.20007秒、最大0.20891秒。

shipsは9件168 state、6件9、8件1。全1,574艦行でmap nx/ny・playerId保持、player indexHits1,574、個別vehicleLookups0。

## 候補IDと範囲差

- 全178 activeでavatar capture complete/count12、候補avatar.idは12件available。候補不明・重複・曖昧一致は0。
- 候補とships[].playerIdの型・値一致数は各stateのships数と同じ（9が168 state、6が9、8が1）。親の独立集計でも候補2,136行中1,574行が同stateのships IDと一致。
- 候補は全2,136行でmeta roster playerIdの値に含まれた。ただしmetaはavatar.id fallbackを使うため、これは独立したnamespace契約の証明ではない。
- **安定後の9艦stateすべて（168件）で、API一覧未一致のavatar候補3行にもmapPosition/health rawがavailable。** 全期間のAPI未一致562行では、map available517、health available562。初期のmap欠測を成功へ書き換えない。
- strict avatar.playerIdは全件unmatchableのまま（確定ID0、apiPresenceUnknown12、confirmed matched0）。candidateConsistencyの値一致はconfirmed joinへ昇格していない。candidate IDのsource/namespace/unverified metadataを保持して扱う。

これにより、24対20と同種の範囲差が今回は12対9として現れ、API艦一覧にないentityの生位置・HPを独立観測として保持できた。API側にその艦行がない理由、一般的なID契約、未出現艦の戦闘状態までは確定しない。alive/位置のroster推測補完は行っていない。

## 性能

profiler available7窓、notSampled171。time.clock / basis assumed、記録時計上の値でCPU使用率・FPSへ換算しない。inclusive phaseを合計しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships（avatar観測・候補生成込み） | 175 | 0.755 | 1.094 |
| avatar | 175 | 2.142 | 3.191 |
| self | 176 | 0.680 | 0.937 |
| armament_systems | 175 | 0.405 | 0.630 |
| torpedoes | 175 | 0.019 | 0.045 |
| submit | 175 | 0.973 | 1.340 |
| snapshot_build_total | 175 | 4.122 | 5.586 |
| state_cycle_total | 175 | 5.119 | 6.806 |

B35等とは実収集艦数・出力内容が異なり、minFPS差をコード起因と断定しない。ユーザー報告上カクつきはなし。B37の魚雷負荷は別資料に保持し、今回発射の再試験は求めていない。

## 次工程

範囲差の追加実機再現は当面不要。raw観測と候補対応を保持する現行出力を基準に、avatar.idの名前空間を既存定義・GUI参照等で確認する。確定契約が見つからなければ、candidateのまま利用者へ明示する。開始直後FPS追跡は引き続き行わない。
