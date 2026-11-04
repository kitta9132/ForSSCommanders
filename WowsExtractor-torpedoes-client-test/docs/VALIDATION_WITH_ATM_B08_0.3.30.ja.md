# ATMありB08：導出state連携の取得確認

2026-11-04。対象は今回の`with-atm-b08.jsonl`。同番号の過去記録とは区別する。ユーザー報告：7:00発射、6:28に1ping、6分台の不明時刻に命中、4:45発射／二重ping、4:08命中。minFPS60以上、カクつきなし。

試験前にcollector9 moduleと復元ATM専用3ファイルをhash照合。試験後はクライアント停止確認後、collector13ファイル＋ATM専用3ファイルを同一backupへ移し、全16ファイルのhashとロード対象外への退避を確認した。PnFModsLoader/TTaroModUtils等の共通依存は変更していない。

## 記録と取得

私有JSONLを逐次解析。0.3.30-atm-derived-state、meta1、roster2、active1,821、inactive終端1。ts177.7369～548.4648（約370.73秒）。平均更新間隔0.20370秒、最小0.20001、最大0.21753秒。

魚雷なし1,465 state、6本341、ほか1～5本の遷移。uiId/shotId/ownerId複合候補12種類、2斉射各6本として初出時刻が分かれる。core魚雷行合計2,094。

- state probe available365、notSampled1,456。候補418行は全exactUiId。
- component/data available278行、none140行。Noneをfalseへ変換していない。
- isHoming：ATM由来判定true162、false116、none140。
- isSpotted：ATM由来推定true108、false170、none140。
- 全stateでdeclaredProducer=advanced_torpedo_marker、producerVerification=notVerified、probe valueKind=thirdPartyDerived。各fieldもguidance assessment／client-side estimateとして分離し、ゲーム／サーバー生値とは扱わない。

ATMなしB41の全componentNoneに対し、ATMありの今回では値の供給と投影が確認できた。ただし汎用componentの書込み元をcollectorが識別したわけではなく、declaredProducerの宣言とインストール条件の照合による実験上の根拠として保持する。

## 供給遅延と操作時刻の限界

最初の6本のcore初出はts357.4658～357.8700、flag値初取得はts379.4917～380.5131（約21.6～23.0秒後）。次の6本はcore初出492.8781～493.6973、flag初取得495.5241～496.5478（約2.0～3.1秒後）。全魚雷が最初から値を持つわけではなく、samplerの1Hzだけでは説明できない初期未供給区間がある。前回値の再利用やfalse補完をしない現契約を維持する。

最初の群はflag初取得時true、その後ts382.5492に全falseへ変化。次群は初取得時true、ts519.9606に混在、520.9771に全false。spottedもfalseからtrueへ変化した。これらはATM側の出力変化を観測したものであり、ping命中・誘導開始／停止の物理時刻・被発見を独立確認したものではない。

ユーザー報告のゲーム残り表示とstate tsに独立同期点はない。とくに1回目の発射→ping報告間隔とflag供給・遷移の順序は、そのまま1対1対応を確定できない。値の供給成功と操作対応／意味検証を分け、命中・消失理由も推測で付けない。

## 性能

time.clock/basis assumed、1,800 cycleの記録時計値：平均2.981ms・最大6.303ms。build平均2.143ms・最大4.830ms、torpedoes平均0.082ms・最大0.630ms、submit平均0.817ms・最大1.979ms。inclusive区間は加算しない。**ATM自身の処理はcollector phase外**であり、この値をATM込み総負荷やFPS改善の証明にしない。ユーザー体感はカクつきなし、minFPS60以上。開始直後FPS低下は追跡していない。

## 判断

任意ATM連携による第三者導出stateの取得可用性とstrict ID対応を確認した。同じ発射／ping試験は繰り返さない。多数艦・敵味方魚雷、供給遅延条件、判定意味・精度は未確認。直接値の未取得項目をATM推定で無言に置換せず、残る取得項目の棚卸しを継続する。
