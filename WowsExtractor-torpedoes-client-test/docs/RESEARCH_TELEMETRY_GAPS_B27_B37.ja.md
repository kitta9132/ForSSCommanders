# 潜水艦・装置情報の既存根拠棚卸し

2026-11-03。B27/B37の匿名集計と既存GUI/API調査資料をLuna xhighが読み取り専用で再確認。新しい実機試験は行っていない。開始直後FPS低下は追跡対象外。

## 再試験不要の取得根拠

- B27のdepth 0→30→0、Battery消費／回復・rate推移は既存記録にある。GUIのm表示とenum labelはUI文脈の根拠に限る。Battery barはvalue/maxCapacity、rate表示は絶対値を参照し、countdownは別countDown経路。容量が百分率、rateが秒当たり百分率と推定しない。
- WaveHitのlifeTimeはUIが直接秒countdown表示する。hitCount 1→2の観測も済み。maxLifeTime-lifeTimeを残時間へ置換しない。
- B27のWaveHit439 snapshotではtargetIDが同snapshotの敵ships.vehicleIdと厳密一致し、playerIdとは不一致。単一target／単一battleの候補整合性として保持する。一般namespace契約の確定や、未取得targetへ自動joinする根拠ではない。
- B27/B37でselfSystemsは全activeにあり、consumable各3行、endTimeはfloat。locatorはobject形状・1行、distShip/workTimeLeftはfloat、stateはint。radar/hydroはunknown。型の確認は単位や未搭載の証明ではない。

## 残るunknownと境界

1. 深度の基準面、物理状態境界、Battery rate単位・容量単位・残時間・枯渇条件は未確定。
2. B27のWaveHitはlifeTime0前に記録終了、rowも残存。GUI isActiveは表示制御でありrow削除・失効条件の契約ではない。
3. WaveHit targetIDのvehicle一致は候補に留める。同一試験を繰り返すだけでは契約を確定できない。
4. 限定GUI定義に区画fieldや対応表は見つからない。FX yaw/hitCountを命中区画として扱わない。
5. API consumable endTimeのtimebase/currentState enumは未確定。B27にtimerCurrentTime候補が共存してもAPI fieldとの時刻基準一致は未証明。GUI CountDownのendTime-Timer.currentTimeを別経路のAPIへ流用せず、endTime-tsも残秒として出さない。Noneと例外を現在unknownへまとめる制約もある。
6. SearchのworkTimeLeft/distShip単位、state意味、object/listのAPI資料差、未搭載と失敗の区別は未解決。

今後の実機操作が必要なら、装置作動表示・UI時間表示・操作遷移を同じ記録に含めることが有用。同条件の深度／二重ping成功試験を理由なく再要求しない。GUI抽出物の版・runtime公開範囲の限界も保持する。

参照：`VALIDATION_0.3.12_B27_SUBMARINE.ja.md`、`VALIDATION_0.3.12_B27_WAVEHIT.ja.md`、`RESEARCH_SUBMARINE_STATE_SEMANTICS.ja.md`、`RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md`、`PERFORMANCE_B37_0.3.26.ja.md`。
