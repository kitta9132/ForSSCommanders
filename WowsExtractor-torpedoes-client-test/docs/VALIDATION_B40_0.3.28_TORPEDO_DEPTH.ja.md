# B40：魚雷深度候補の取得確認

2026-11-04解析。ユーザー報告：6対6、8:22に全発射完了、7:30退出、minFPS60、カクつきなし。実際のrosterは12隻。ゲーム残り時刻とstate tsは直接変換しない。クライアント停止確認後、mod13ファイルをhash照合してロード対象外へ保全退避。

## 記録

私有JSONLを逐次解析。0.3.28-torpedo-depth-sampling、meta1、active733、inactive終端1。ts1653.7004～1803.0219（約149.32秒）、平均更新間隔0.20399秒、最小0.20003、最大0.21716秒。

ships件数は10が435 state、9が282、6が15、8が1。魚雷なし510 state、6本213、ほか1～5本の遷移。魚雷有観測はts1750.1040～1795.4693。これは観測期間であり直接取得した魚雷寿命ではない。

## depth候補

- probe available147、notSampled586。全due collectionはavailable、CCキーもavailable。
- due時の候補262行は全てdepth available、API/UI一意の型・値一致によるexactUiId262件。
- raw値は全件0.14、unitは全件null。浮上発射の今回の観測であり、他深度での変化・物理的基準面・単位は未確認。
- core魚雷1,307行のうちdepth付与262、その他1,045行は当該stateでdepthなし。1Hz sample外で古い値を再利用しない方針による。depthなしを0や海面へ補完しない。
- position.yからdepthの意味を代用しない。対象艦深度・深度差・誘導停止深度の取得成功へ拡張しない。

## 負荷と制約

profiler725 cycleの記録時計値：cycle平均5.775ms・最大21.938ms、build平均4.645ms・最大18.330ms、torpedoes平均0.116ms・最大1.430ms、avatar平均2.336ms・最大8.694ms、ships平均0.853ms・最大3.092ms、submit平均1.102ms・最大3.557ms。time.clock/basis assumed、inclusive区間を加算しない。ユーザー体感はカクつきなし。最大値をdepth起因と断定せずFPSやCPU使用率へ換算しない。開始直後低下は追跡しない。

独立depth取得の実機可用性と一意ID一致を確認した。同じ浮上発射試験の再要求は不要。意味・単位・深度変化は未完了として残し、次の未検証情報と同時に確認できる場合だけ新しい操作条件を計画する。
