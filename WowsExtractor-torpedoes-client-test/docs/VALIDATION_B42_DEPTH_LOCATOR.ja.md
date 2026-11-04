# B42：魚雷depth候補とlocator作動の記録

2026-11-04。ユーザー報告：8:30発射、8:00に深度0m、4:28に装置作動、効果終了前退出。minFPS60以上、カクつきなし。発射時のHUD深度と作動直後のHUD残秒は明示されていない。試験指示の30mを実施済みと推定しない。終了後クライアント停止確認・mod13ファイルhash照合退避済み。

## 記録と魚雷

私有JSONLを逐次解析。0.3.30-atm-derived-state、meta1、roster2、active1,784、inactive終端1。ts561.8509～925.2377（約363.39秒）、更新間隔平均0.20381秒、最小0.20000秒、最大0.21459秒。ATM・state sampler・heavy diagnostics・profilerはOFF、depth sampler1Hz。

魚雷候補1本、coreで218 state観測。depth probe due357回、notSampled1,427回。魚雷のdepth候補43行は全available/exactUiId、rawは全0.14、unitはnull。B40と同値だが、発射時自艦深度・その後魚雷が進む深度・depth fieldの意味を同一視しない。selfSubmarineProbeは全stateでdisabledなので、記録から発射時自艦深度は独立確認できない。

## locatorと消耗品

- 初回ts561.8509：search state6、workTimeLeft0、distShip200。消耗品の対応候補rowもcurrentState6、endTime-ts330。
- ts892.0108：search state0、対応消耗品currentState0、endTime-ts0。
- ts892.4176：search state3、workTimeLeft60、対応消耗品currentState3、endTime-ts60。
- 最終ts925.2377：search state3、workTimeLeft27.87854、対応消耗品endTime-ts27.87854。効果終了前退出の報告と整合。作動終了・cooldown遷移は未観測。

state3の162 sample全てで`endTime - state.ts - workTimeLeft`は記録上厳密0。ただし**endTime自体は952.4093～953.4083の約1秒幅で変動する**。したがって、不変のdeadlineとして保存して現在時計だけでcountdownを外挿できる保証はない。getter内部の生成方式も公開sourceで未確認。同snapshotのAPI数値整合と、HUD秒数／一般timebase契約を分ける。

汎用GUI enumの状態名やm/km/秒単位は対応するAPIとの静的配線／画面照合がない限りrawへ無条件付与しない。今回はHUD残秒の独立照合はできない。開始FPSや同じping・浮上発射試験を追加要求しない。

## 残る確認

作動とraw状態遷移、same-snapshotの時間値整合は記録できた。終了・cooldown、HUD残秒、発射時HUD深度の未報告分は未確認のまま残す。手元の記録やユーザーの既存観測で補えるものを先に扱い、約330秒の待機試験を直ちに繰り返させない。
