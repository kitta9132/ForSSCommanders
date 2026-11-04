# 0.3.38 限定実機確認（未実施）

目的はソース変更後のruntime可用性と通常区間の負荷確認。開始直後FPS低下の調査を再開しない。実機で未確認の初回性能取得／独立probe／群別cadenceを1戦へまとめ、装填数・深度意味・WaveHit TTLの既知の未知を再調査する試験ではない。

## 条件

- mod `0.3.38-independent-gun-reload`、source commit `ae3c9e8`。予定build `13357625`（直近clientrunnerの起動実績で確認。別buildへの切替時は再確認）。
- ATMなし。既存の他modを一括削除しない。
- Undine、訓練戦1対1、10分、敵botは攻撃ON・可能なら魚雷装備艦。直ちに大量魚雷／高負荷条件を再現しない。
- `collection_enabled=true`, `diagnostics_enabled=false`, `profiler_enabled=true`, `state_interval=0.2`。
- `self_depth_sampling_enabled=true`, `battery_sampling_enabled=true`, `wave_hit_sampling_enabled=true`, `gun_reload_sampling_enabled=true`。
- 独立魚雷深度・ATM state samplerとposition fallbackはOFF。新設定4群だけを明示ONにする。
- 外部recorderは全fieldを保存。古いstate/metaと新battleを混ぜず、battleIdとmod.versionを照合する。AIが導入・hash照合・記録起動・解析・終了後退避を担当する。

## 操作（ユーザー）

1. 戦闘前に魚雷選択を強制しない。開始後は9:30まで通常移動し、追加発射・pingはしない。初回paramsの失敗を後から再取得で埋めない実装の確認。
2. 9:30ごろに魚雷1斉射。9:20ごろに敵へpingを1回当てる（難しければ外れ／未命中と報告するだけで再試行を繰り返さない）。独立gun／WaveHitの**新しい経路**確認であり、旧heavy経路の成功試験を同条件で繰り返す目的ではない。
3. 9:00ごろに30mへ潜航。8:30ごろまで普通に航行して退出する。長いcooldown・TTL失効待ちはしない。
4. 通常区間の最低FPS・目立つカクつき有無、発射／ping命中／潜航／退出のおよその時刻を報告。録画も提供する。悪化・操作支障があれば即退出して終了してよい。

## AIの確認

- metaの初回ammo／TTXがavailableかunknownか。unknownを0／別sample由来値で補わない。初回だけという契約と可用性を区別する。
- heavy OFFで4群が出るか。depth／WaveHit／gunは実core周期、Battery／damage／比較は約1Hz、HPは平均約2Hz。時刻差の分布と非dueを確認する。
- gunのgetEntity参照探索なし、raw state／progress取得、同tick二重probeなしのoffline根拠を維持。loaded countや物理管番号へ昇格しない。
- WaveHitの列挙・rawと群別時刻を確認し、heavy OFFでidentityCandidatesを確定対象として追加しない。命中がなければ空列挙と可用性を分ける。
- profilerのsubmarine_sampling／gun_sampling、通常区間のcycle／submitを確認する。過去戦との差を因果的なFPS改善と断言しない。
- 魚雷のnear/far双方が自然に観測できた場合のみ距離群と実sample間隔を検証する。片方だけなら未確認を保持し、このための高負荷再戦を即要求しない。
- 終了frameに最新damageが出るか。記録回収後にゲーム停止確認・導入ファイルhash照合・collector退避を実施する。

## 現在の準備状態

全555 offline tests／9 module checker成功。ゲーム停止を確認し、11 source fileのinstaller用SHA256を再生成（ZIPなし）、build13357625へのread-only dry-run成功。

準備更新：既存installer経由で導入後、Python9＋config.exampleの10ファイルをソースとSHA256一致確認。既存loaderは維持、ATMロード対象なし。新規config.iniに上記試験設定を書き込み、全field recorderをprefix `without-atm-b`で起動（最大3600秒、番号自動採番）。ゲーム停止は設定書込み前にも確認。**実機操作・実機結果は未実施。** recorder期限後に開始する場合はAIが再準備する。
