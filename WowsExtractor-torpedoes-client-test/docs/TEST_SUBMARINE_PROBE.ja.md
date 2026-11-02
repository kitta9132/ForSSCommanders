# 潜水艦probe：最小実機確認

対象は`0.3.12-collection-compat`。最初の確認は操作をせず、Undineで記録を約20秒だけ行い、先に`selfSubmarineProbe.collection`のstatus/reasonと`waveHitProbe.collection`のstatus/reasonを確認します。列挙修正後に取得できるかの最短確認が目的です。statusが取得成功を示すまで、再潜水やping操作は行いません。

取得成功（自艦collectionが完全なsingleton、WaveHit collectionがavailable）を確認できた場合だけ、必要に応じて別の短い記録で、通常の訓練戦のUndineを使い次を安全・可能な範囲で行います。値の意味・単位の確定は目的ではありません。

1. （0.3.12では取得成功を確認した後に限る）浮上、潜望鏡深度、最大深度をそれぞれ短時間保持し、その後浮上して回復を待つ。負担なら深度/Batteryだけで終了してよい。
2. 可能なら停止中bot一隻へpingを1回、別フェーズで2回行う。負担・危険なら省略可。ターゲット識別や攻撃は不要。
3. 既存のship health/position等の出力が保たれていることも確認。JSONLを記録し、各操作時刻の`selfSubmarineProbe` status/sampleTs、Submarine/Battery各field status/raw値、`waveHitProbe` collection/row statusと画面上の深度・Battery/ping表示をメモする。

`available`はPython経路からraw値を読めたことだけを示します。意味・単位は未確認です。unknown/unsupported/emptyもそのまま報告してください。`targetID`をshipへjoinしない、座標y=0を深度にしない、WaveHit lifetimeから残時間を作らない、Battery rateの符号・残量/時間を推定しないでください。

報告にはmod version、game build、艦、記録開始/終了と操作順、表示値、各probeのstatus・fieldStatusを含めます。ログ共有時は個人情報やentity/player IDを匿名化してください。B18のparameter selector複合key修正はraw B18記録で取得済み・offline選択確認済みのため、0.3.10経路の実機再試験は今回不要です。
