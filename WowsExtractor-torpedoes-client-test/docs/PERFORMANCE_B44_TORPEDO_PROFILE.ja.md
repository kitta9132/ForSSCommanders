# B44：多数魚雷の区間計測

2026-11-04。ユーザー報告：7:30退出、minFPS40～50、目立つカクつきなし。0.3.30のcore5Hz、profiler ON、heavy/depth/state samplerとATMはOFF。終了後クライアント停止確認・collector13ファイルhash照合退避済み。

## 記録

私有JSONLを逐次解析。meta2件roster12、active743、inactive2、範囲約151.76秒。shipsは6件419 state、12件303、ほか7～10件。魚雷同時最大63本、owner同時最大11、全9,671魚雷行でworld/map positionを保持。平均更新間隔0.20453秒、最大0.22068秒。

profiler available29窓、notSampled714。writerMode syncEncodeWrite、time.clock/basis assumed。以下は記録時計上の値でCPU使用率・FPSへ換算しない。inclusive区間は合計として加算しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships | 725 | 1.636 | 3.472 |
| avatar | 725 | 2.167 | 5.935 |
| torpedoes | 725 | 0.441 | 2.310 |
| submit | 725 | 1.186 | 2.327 |
| snapshot_build_total | 725 | 5.612 | 11.346 |
| state_cycle_total | 725 | 6.825 | 12.423 |

## 増加の内訳

最初の窓は魚雷0本・ships平均0.662ms、cycle5.163ms。魚雷がまだ0本の後続窓でもships平均が約1.96msまで増え、avatarはおおむね2.1～2.3ms。魚雷だけが原因とは限らず、較正sample蓄積等のsource内経路を再生で調べる必要がある。

魚雷が増えた終盤の最後のcomplete窓（出力ts643.0633）は魚雷平均61.6本・最大63本・owner11。torpedoes平均2.056ms／最大2.310ms、submit平均1.894ms／最大2.190ms、ships平均1.977ms、avatar平均2.047ms、cycle平均9.319ms／最大10.333ms。魚雷初期0本窓のtorpedoes約0.025～0.034ms、submit約0.93～1.09msに対し増加を観測した。

窓の魚雷数は対応するstate区間を集計したもので、profilerのphase完了と出力の境界差があり、個々の魚雷への厳密な時間帰属ではない。216本を観測したB43へ直線外挿して時間を確定しない。描画・他game処理・recorderはcollector phase外であり、報告minFPSとの因果は未確定。

## 次工程

追加実機を直ちに要求せず、魚雷がない区間でも増えるships費用を既存記録の較正replayで調べる。B31でreservoirが小さい条件ではduplicate scan主因説は支持されなかったため、今回も比較回数とearlyreturnを実測し、条件差を明記する。意味・coverageを保った削減が成立する場合だけsourceを変更する。魚雷切捨てやframeを超えた古いowner/positionの再利用はしない。
