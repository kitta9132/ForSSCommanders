# B41：魚雷state候補はcomponent実体None

2026-11-04。ユーザー報告：08:00発射、07:40に1ping、07:30頃に外れを確認、07:00に二重状態で発射、06:40頃命中。minFPS60、カクつきなし。時刻はユーザーのゲーム内表示で、state tsとの直接変換や命中イベントの確定には使わない。試験後クライアント停止を確認し、mod13ファイルをhash照合してロード対象外へ退避。

## 記録

私有JSONLを逐次解析。meta1、0.3.29-torpedo-state-sampling、roster2。active1,277、inactive終端1。ts179.3882～439.3428（約259.95秒）。平均更新間隔0.20373秒、最小0.20001、最大0.21226秒。

魚雷なし859 state、1本418。uiId/shotId/ownerIdの複合候補は2種類（241行・177行）。出現／消失はts293.9256→342.9301、345.3739→381.4260。これらは観測期間であり、射程切れ／命中や誘導停止理由の直接取得ではない。

## 候補の取得状況

- torpedoStateProbe available256、notSampled1,021。due collection256件は全available、CCキーも全available。
- 魚雷候補84行は全てexactUiIdでAPI行と対応。ただし**componentStatus=none、dataStatus=noneが全84行**。
- isHoming/isSpottedの各fieldは全84行status=none、raw=null、type=null。全core魚雷418行の投影値もNone。
- これはfalseや非誘導／未被発見ではない。CCキーの存在とcollection取得、ID対応は確認できたが、対象entityのmods_DataComponent実体がNoneでフラグ値を取得できていない。
- producer不在、UI専用componentの可視範囲、キー／参照経路等の原因は記録だけでは確定しない。操作を誤った根拠はなく、同じ発射／ping試験の再要求はしない。

## 性能と次工程

記録時計time.clock/basis assumed、1,275 cycleの平均2.895ms・最大5.804ms。build平均2.075ms・最大3.741ms、torpedoes平均0.056ms・最大0.214ms、submit平均0.798ms・最大2.273ms。inclusive区間は加算せず、FPSへ換算しない。ユーザー体感はカクつきなし。開始直後FPS低下は追跡しない。

魚雷フラグの実取得は未達。次は既存GUI/ATM定義・producerと別API経路をread-onlyで調べる。ATMなしでもcomponentがpopulateされると仮定しない。第三者modの導入や推測値による代用は行わない。B40で成功したdepth候補の取得は別経路であり、今回のNoneから否定しない。
