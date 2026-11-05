# ATMありB09：12対12負荷・距離1/3条件の実効性

2026-11-05、collector `0.3.38-independent-gun-reload`、build13533378（15.10）。[試験構成・公式配布物の固定commit](VALIDATION_PLAN_13533378_ATM_12V12.ja.md)。heavy OFF、独立4群・profiler ON、core0.2秒、ATM state1Hz。private記録は199,389,730byte・1,850 records。個人ID・氏名・生ログ・第三者本体は公開しない。

## 報告とセッションの区別

ユーザーはbot同士の魚雷戦を観察し、ソナーで魚雷を発見。自艦の発射・ping試験ではない。申告では1回目は拠点未設定でbotが逃げ合い、2回目が正常。minFPS約40では目立つカクつきなし、負荷増加で約30になると体感するカクつきが発生した。FPS時系列・同期録画はないため、特定の集計窓をmin30区間と断定しない。

記録上はmeta3件・battleId3種。開始時のself HP・API ships範囲のリセット、終了frame、間の空白から別セッションとして扱うが、ID数だけでユーザー申告の回数を訂正したり、出現順2番目を主評価と断定しない。魚雷のあった後続2セッションを分けて示す。

| 記録セッション | observedAtの日本時間 | active state数 | active範囲 | 最大魚雷membership |
| --- | --- | ---: | ---: | ---: |
| S1・準備／参考候補 | 09:31:29～09:32:20 | 247 | 約50.6秒 | 0 |
| S2・魚雷あり | 09:35:32～09:38:41 | 919 | 約188.4秒 | 92 |
| S3・魚雷あり／最終セッション | 09:45:02～09:47:21 | 677 | 約138.6秒 | 95 |

3セッションともmeta roster24・12対12、艦種構成はKleber23＋Minotaur1、地図Ocean。ここでいう魚雷本数は公開APIの観測membershipであり、ゲーム内の全魚雷数保証ではない。**今回200本同時を観測した区間はなく、記録上最大95本**。

## 距離1/3条件は働いたが、約85%が近距離

各active stateでmembershipComplete=true、API status=available、重複／照合不能IDなし。以下は魚雷のユニーク総数ではなく、各stateのmembership／sample行を合算した値。

| 指標 | S2 | S3 |
| --- | ---: | ---: |
| 最大membership | 92 | 95 |
| ピーク時high／low | 75／17 | 78／17 |
| ピーク隣接のlow非due tickのdetail行数 | 75 | 78 |
| membership合計 | 18,383 | 15,211 |
| 今回sampleしたdetail行合計 | 16,904 | 13,844 |
| high membership合計 | 15,895 | 12,921 |
| low membership合計 | 2,488 | 2,290 |
| far非dueで省いたdetail行 | 1,479 | 1,367 |
| 全membershipに対する省略率 | 8.05% | 8.99% |
| lowだけの省略率 | 59.45% | 59.69% |

highのdetail省略は0。lowは約60%を省略できているが、そもそも全membershipの約15%しかないため、全体削減は約8～9%だった。**本数を1/3へ絞る方式ではなく、半径をマップ短辺の1/3にする方式**である。farを全廃しても残るdetail行の約6～7%しか減らず、取得範囲を失う割に効果が小さい。

分類半径は較正由来で約400 game_world、マップ一辺のscaleは約1200。mapSource=calibratedMapExtents／mapInferred=trueであり、公式の物理km境界と保証しない。分類context unknownはS2初期約4.9秒／S3約20.3秒だが、いずれも魚雷初出前。今回のnear偏りをcontext不明のhigh fallbackでは説明しない。5秒再分類のため、その間の境界越えは設計上あり得る。

low間隔は中央値の逆数をHzとして読まない。親がlow memberの連続存在区間内で隣接sample差を集計すると、S2は157間隔・min0.400516／median0.424786／mean0.512110／max0.643955秒、S3は99間隔・min0.401232／median0.424839／mean0.513412／max0.632610秒。平均ベース約1.95Hzで、tick量子化された平均2Hz枠として動作している。個々の魚雷の寿命・枠移動を混ぜた中央値だけから2.3Hz等と評価しない。

## collector負荷：魚雷で増える費用と固定費

performance窓はsampleStartSeconds／sampleEndSecondsで重複除去。S2は36窓、S3は27窓。表の平均はphase totalの合計／countの合計、time.clock／basis=assumed、writerMode=syncEncodeWrite。親子phaseは入れ子であり加算しない。

| phase | S2平均ms | S3平均ms |
| --- | ---: | ---: |
| state_cycle_total | 10.711 | 10.661 |
| snapshot_build_total | 8.728 | 8.714 |
| avatar | 4.062 | 4.005 |
| ships | 1.516 | 1.497 |
| torpedoes | 1.150 | 1.232 |
| submit | 1.957 | 1.922 |
| gun_sampling | 0.721 | 0.719 |
| self | 0.709 | 0.705 |
| armament_systems | 0.246 | 0.244 |
| submarine_sampling | 0.130 | 0.129 |

魚雷0の窓と、窓内最大membershipが10以上の窓を比べると、cycleはS2約9.08→12.48ms／S3約8.86→13.22ms。torpedoes増分は約2.20／2.78ms、submit増分は約0.88／1.08ms、ships増分は約0.37／0.42ms。avatarはほぼ4msのまま。これは魚雷数で分類した窓の比較で、FPS区間と同期した対照実験ではない。

高負荷の集計窓でcycle平均は最大約15.47ms（S2）／15.14ms（S3）。S2／S3全体での単発cycle最大は23.67／17.59ms。**5Hz前後の取得tickにまとまった費用が載る**ことは確認できるが、これだけで体感カクつきの全原因をcollectorと断定しない。ATM本体の更新・描画、ゲーム本体の処理はcollectorの計測外。

## ATM供給・上限の扱い

新buildのログでcollector0.3.38のロード、ModForgeのinstalled=1／failed=0を確認し、当日の保存ログにTracebackは検出しなかった。これを全エラー不存在や将来の互換保証としない。

- ATM state dueはS2 available161／truncated23、S3 available112／truncated24。他tickはnotSampled。UI候補の上限64は公開API membershipとは別枠。
- 候補行はS2計3,417／S3計2,682。mods_DataComponent/data availableは585／446、noneは2,832／2,236。available分ではisHoming=false／isSpotted=trueを観測し、noneをfalseへ補完していない。
- candidate apiMatchStatusはS2 exactUiId1,172／collectionIncomplete1,472／notSampled773、S3 exactUiId1,146／collectionIncomplete1,536。far非dueのsubsetやUI列挙上限による不完全性を、確定joinや魚雷消失へ変換しない。
- 判定はdeclared producer advanced_torpedo_marker／producerVerification=notVerifiedの第三者導出値。今回のソナー操作と個々のflagを時刻同期していないため、ソナーでの検出を当該flagが直接示すとは断言しない。

## 判断・次工程・撤収

1/3条件の不作動ではなく、**条件は働いたが約85%がnearだった**。200本を今回の実測として扱わず、95本時でも体感悪化が報告された点を残す。近距離detailに本数budgetを付ける案は回避に必要な観測を減らすため、未承認・未採用とする。現在の半径・周期も無断変更しない。

次は追加の実機負荷再現ではなく、情報を維持したまま約4msのavatar固定費や同期serialize／write費用を減らせるかコードで調べる。無駄なread／構築の削減余地と、API内部費用で削れない部分を分ける。B46は旧build・ATMなし・少数艦で条件が違うため、因果的FPS改善率を計算しない。

記録を回収して記録プロセスを停止。ゲーム停止確認後、collector10 source hash一致・今回の第三者配布ファイルの改変なしを確認した。導入前が空だった新build内で、導入manifestとModForge生成UI／cacheに属することを全件確認し、145ファイルをhash照合してload path外へ退避。旧buildは触らず、ModPrefsの手動変更・削除も行っていない。
