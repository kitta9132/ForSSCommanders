# B48 L/5 実記録解析（0.3.40-radius-l5）

2026-11-07、記録 `recordings/without-atm-b48.jsonl`（129,060,476 byte、901 records）。modバージョン `0.3.40-radius-l5`。ユーザー報告は 11v12 超重負荷（シャトルーノー）／TrainingBattle、一方で記録metaは12対12 roster24・自艦Minotaur。両者をユーザー報告／記録値としてそのまま記載し、実動艦数等を推測しない。FPS・体感報告なし→**unknown**として扱う。解析は匿名集計のみで、battle ID・player ID・vehicle ID・weapon ID・生ログは公開しない。

## 記録構成と除外

| 項目 | 値 |
| --- | --- |
| 総records | 901（meta 2 / state 899） |
| battle ID種 | 2（S1とS2で異なる） |
| マップ | IDS_SPACES/00_CO_OCEAN |
| モード | GAMEMODE_AWESOME / TrainingBattle / 12対12 |
| roster | 24隻（Destroyer 23 / Cruiser 1） |
| 自艦 | Minotaur |
| 相手艦種 | Chateaurenault ×23 |
| modバージョン | `0.3.40-radius-l5` |
| build | **jsonlにbuildフィールドなし**。同日の既存資料では13533378（15.10）と記録されているが、今回の記録からは実確認できない |

| セッション | 状態 | active state数 | 期間 |
| --- | --- | ---: | ---: |
| S1 | **旧meta混入のため除外** | 0 | — |
| S2 | 解析対象 | 897 | 約185.1秒 |

S1は別battleIdのmetaの直後に1つだけinactiveなstateがあり、魚雷・performanceとも空なので解析から除外する。

## 半径・距離条件の実確認

`torpedoStatus.sampling.classification`から半径を実確認した。ファイル名だけでATM不在／L/5適用を決めない。

| 項目 | 実測値 |
| --- | ---: |
| radiusWorld | 239.977 |
| 較正地図短辺 L | 1,199.885 |
| L / radiusWorld | **5.0**（847 stateで一致） |
| mapSource | `calibratedMapExtents` |
| mapInferred | `True` |

**半径は記録から L/5 で動作していることが確認できた。**

## 魚雷本数：延べ・同時最大・ユニーク

| 指標 | S2 |
| --- | ---: |
| membership延べ行 | 67,970 |
| detail sample延べ行 | 47,135 |
| 最大同時membership | **280** |
| 最大同時detail | 280 |
| 最大owner数（1 stateあたり） | 23 |
| ユニークidentity | 317 |
| ユニックowner | 24 |

B09（S2/S3）の最大 92／95 本に対し、B48では最大 **280** 本を観測。同じ12対12構成でも艦級（Chateaurenault vs Kleber）・魚雷本数が大きく異なる。

## 距離分類tickのL3 vs L5幾何比較

分類tick（classification.ts == state.ts）で、現在全positionsを比較した。完全なcounterfactual replayではなく、**分類tick現在全位置**に限る。contextMissingでradiusのない2 tickはskip（行数0）。

| 指標 | S2 |
| --- | ---: |
| 分類tick総数 | 37 |
| 利用可能tick | 35 |
| skip tick | 2（contextMissing、行数0） |
| 分類tick行数合計 | 2,891 |
| L5 near（d ≤ L/5） | 1,261（**43.6%**） |
| L5 mid（L/5 < d ≤ L/3） | 1,625（56.2%） |
| L5 far（d > L/3） | 5（0.2%） |
| L5 unknown距離 | 0 |
| L3 near（d ≤ L/3） | 2,886（99.8%） |
| L3 far | 5（0.2%） |
| band / L3 near | 56.3% |

| 同一分類tickの実HIGH／LOW | 値 |
| --- | ---: |
| 実HIGH member / sampled | 1,264 / 1,264 |
| うち L5 near | 1,261 |
| うち L5 mid（非near HIGH） | 3 |
| 実LOW member / sampled | 1,627 / 1,627 |
| うち L5 mid | 1,622 |
| うち L5 far | 5 |
| LOW near | 0 |

**L5 near 43.6% は、以前のB09に対する静的L/5試算（40.5–44.4%）と同じ範囲内／近い値である。** ただし条件が異なり、これを「L/5の効果が確認できた」とは扱わない。B09実記録のL3 nearは約85%であり、B48の実測はL5適用後の分布であって、B09 L3の分布と混同しない。

## own全距離例外と新規／unknown HIGHの分離

B48では **`isOwn` は全47,135行で `None`**、`owner.isPlayer` も全行で `None` であった。したがって：

- **自艦own全距離HIGH例外の観測根拠は本記録にない**。`isPlayer=True`がstrictに適用されたかどうかは別の確認が必要。
- 分類tick上の非near HIGHは **3件（0.1%）**。これらがown例外、新規／provisional HIGH、あるいはwire上の理由によるものかは記録から分離できず、原因未確定。
- unknown距離のHIGHは **0件**。

全sample行で見ると、HIGHかつL5外（mid/far）は **2,708件（HIGHの8.4%）**。これらは5秒ごとの再分類ラグの可能性があるが、新規／provisional HIGHも排除できない。分類直後のtickでは3件に縮まるのみで、個別の原因は未確定。

## far非due省略とdetail比率

| 指標 | S2 |
| --- | ---: |
| membership合計 | 67,970 |
| detail行合計 | 47,135 |
| 省略行（membership - detail） | 20,835 |
| membershipに対する省略率 | **30.7%** |
| detailに対する省略率 | 44.2% |
| HIGH member / sampled | 32,305 / 32,305（省略0） |
| LOW member / sampled | 35,665 / 14,830 |
| LOW省略率 | **58.4%** |

B09 L3では全membership省略率が約8～9%だった。B48では30.7%と高いが、条件が大きく異なる。L5がfar/lowの割合を増やした幾何的な可能性はあり、分類tickのL5 near 43.6%がその裏付けになるが、30.7%と8–9%の差全体をL5の因果効果と断定しない。stateあたりのdetail／membership比の中央値は 0.60（membership>0のstateのみ）。

## 連続identity sample間隔

| グループ | n | min | p10 | median | mean | p90 | p95 | max | >1s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HIGH | 31,988 | 0.200 | 0.202 | **0.208** | 0.209 | 0.215 | 0.218 | 0.633 | 0 |
| LOW | 14,830 | 0.201 | 0.410 | **0.429** | 0.502 | 0.633 | 0.635 | 0.655 | 0 |
| 全体 | 46,818 | 0.200 | 0.202 | 0.211 | 0.302 | 0.618 | 0.628 | 0.655 | 0 |

HIGHは約5Hzで動作しており、1秒を超える間隔はない。LOWは中央値0.429秒、平均0.502秒で、平均から約1.99Hzとして扱う。medianの逆数（≒2.33Hz）を実sample frequencyとは見なさない。B09のLOW median 0.425s／mean 0.512sと同じ水準。

## 位置欠測とmotion availability

| 項目 | 値 |
| --- | ---: |
| world position欠測（非有限/None） | 0 / 47,135 |
| mapPositionStatus unknown | 826（LOWのみ、1.75%） |
| motion unavailable | 317（HIGHのみ、初回sample等） |
| speed missing（motion available時） | 0 |

## 有効probes・provider・flags

| probe | status（state数） |
| --- | --- |
| gunReloadProbe | available 897 |
| waveHitProbe | available 897 |
| torpedoStateProbe | available 106 / notSampled 717 / truncated 74 |
| performance | available 36 / notSampled 861 |
| gameClockProbe / identityCandidates / torpedoDepthProbe / uiTorpedoProbe / weaponContextProbe / weaponHubProbe | disabled 897 |
| selfSubmarineProbe | unknown 897（自艦が潜水艦でない） |

provider／flagsの実確認：

- torpedoStatus.source = `battle.getAllTorpedoes`（897 state）
- membershipComplete = `True`（897 state）
- torpedoStateProbe.declaredProducer = `advanced_torpedo_marker`（897 state）
- torpedoStateProbe.producer = `unknown`、producerVerification = `notVerified`
- uiTorpedoProbe = disabled、source = `config.diagnostics_enabled`
- DataComponent rows：available 2,292 / none 2,677（flags isHoming/isSpotted同数）

**filenameの `without-atm` だけでATM不在とは決められない。** DataComponentにproviderデータが2,292行存在し、declaredProducerはATMのものだが実producerはunknown／notVerifiedである。

performance writer：writerMode `syncEncodeWrite`、timebase `time.clock`／`assumed`、durationUnit `ms`、resolutionStatus `observedNotGuaranteed`。36の完成済み5秒窓はsampleStart／sampleEndで重複除去され、重複なし。

## performance：5秒窓加重平均と重い同一窓

| phase | 加重平均ms | totalCount | 単発max | 窓平均median | 窓平均p95 | 窓平均max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| state_cycle_total | 14.284 | 890 | 39.513 | 10.148 | 25.114 | 25.273 |
| snapshot_build_total | 11.539 | 890 | 32.600 | 8.363 | 19.984 | 19.989 |
| avatar | 4.203 | 890 | 7.996 | 4.180 | 4.419 | 4.435 |
| ships | 1.657 | 890 | 5.015 | 1.770 | 2.013 | 2.036 |
| torpedoes | 3.547 | 890 | 18.077 | 0.112 | 11.544 | 11.784 |
| submit | 2.716 | 890 | 7.683 | 1.756 | 5.260 | 5.378 |
| gun_sampling | 0.745 | 890 | 1.907 | 0.747 | 0.788 | 0.808 |
| self | 0.741 | 891 | 1.172 | 0.740 | 0.792 | 0.792 |
| armament_systems | 0.266 | 890 | 2.667 | 0.264 | 0.290 | 0.356 |
| submarine_sampling | 0.143 | 890 | 0.318 | 0.142 | 0.164 | 0.169 |

36窓中19窓はmembership 0、17窓が正のmembership。最もcycle平均が重かった1窓（membership 276、5.112秒）：

| phase | 平均ms | 単発max | count |
| --- | ---: | ---: | ---: |
| state_cycle_total | 25.273 | 32.778 | 24 |
| snapshot_build_total | 19.984 | 25.217 | 24 |
| avatar | 4.135 | 4.594 | 24 |
| ships | 1.825 | 2.225 | 24 |
| torpedoes | 11.784 | 17.124 | 24 |
| submit | 5.257 | 7.621 | 24 |
| gun_sampling | 0.748 | 0.874 | 24 |
| self | 0.728 | 0.932 | 24 |
| armament_systems | 0.266 | 0.303 | 24 |
| submarine_sampling | 0.162 | 0.264 | 24 |

## 魚雷本数帯別の近似比較（state.tsとperf clockのoffset 24.9秒）

state.tsとperformanceのsampleEndSecondsは別時計。carrier stateの `ts - sampleEndSeconds` は 24.903–24.926秒でほぼ一定（median 24.922秒）。以下はこのoffsetを使った近似対応で、**厳密な同一時刻の相関ではない**。

| 帯（membership） | 窓数 | 平均membership | cycle平均ms | torpedoes平均ms | submit平均ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 19 | 0 | 9.36 | 0.11 | 1.52 |
| 1–49 | 1 | 13 | 10.98 | 0.36 | 1.94 |
| 50–99 | 3 | 72 | 13.58 | 2.80 | 2.61 |
| 100–179 | 4 | 140 | 18.00 | 6.14 | 3.58 |
| 180+ | 9 | 233 | 24.02 | 10.54 | 5.07 |
| 正のmembership | 17 | 170 | 19.93 | 7.49 | 4.08 |

## B09 L3（0.3.38・ATMあり）との比較

| 指標 | B09 S2 | B09 S3 | B48 S2（0.3.40 L5） |
| --- | ---: | ---: | ---: |
| 最大membership | 92 | 95 | **280** |
| membership延べ | 18,383 | 15,211 | 67,970 |
| detail延べ | 16,904 | 13,844 | 47,135 |
| near（実測/分類tick） | **約85%** | **約85%** | **43.6%**（L5分類tick） |
| HIGH member割合 | 86.5% | 84.9% | 47.5% |
| 全membership省略率 | 8.0% | 8.99% | **30.7%** |
| LOW省略率 | 59.5% | 59.7% | 58.4% |
| cycle加重平均ms | 10.711 | 10.661 | **14.284** |
| 最重窓cycle平均ms | 15.469 | 15.141 | **25.273** |
| 単発cycle max ms | 23.673 | 17.592 | **39.513** |
| LOW median間隔 | 0.425 | 0.425 | 0.429 |
| LOW mean間隔 | 0.512 | 0.513 | 0.502 |

**構成差**（B48 vs B09）：

- 艦級が異なる（Chateaurenault ×23 vs Kleber ×23、いずれもMinotaur×1）
- 最大魚雷本数 280 vs 92/95（約3倍）
- 半径 L/5 vs L/3
- ATM：B09はATM併用、B48はfilename `without-atm` だが記録からATM不在は実証できない
- probes：B48ではtorpedoStateProbeが1Hzで動作し、gunReload/waveHitが有効；B09はATM state 1Hz
- own例外：B48では `isOwn`／`owner.isPlayer` が観測できず、自艦全距離HIGHの実機動作は確認できていない
- modバージョン 0.3.40-radius-l5 vs 0.3.38

したがって、cycleがB09より大きいからといってL/5が悪化したとは言えないし、省略率が上がったからといって因果的なFPS改善率とは扱わない。

同帯の近似比較：B48の 50–99 membership 帯（cycle 13.58ms / torpedoes 2.80ms）と、B09のmembership 10以上帯（cycle 12.48／13.22ms、torpedoes増分 2.20／2.78ms）を比較しても、B48が明らかに速くなっているわけではない。負荷はおもに魚雷本数の増加に追従している。

## どこが効いたか

1. **半径は記録から L/5 で動作している**（L/radius=5.0）。
2. **距離分類は設計どおり**：分類tickではL5 near 43.6%、HIGHはほぼnear、LOWはmid/far。以前のB09 L/5幾何試算（40–44%）と同じ範囲内／近い値。
3. **5Hz detailは減少**：membershipに対するdetail比率が69.3%（B09は約91–92%）。HIGHは全tick 5Hz、LOWは約2Hzで、省略はfar/low non-dueによる。
4. **LOW cadenceは安定**：median 0.429s、1秒超のgapなし。

一方、**B48では最大280本の魚雷があり、perfのcycleはB09より重い**。L/5によるdetail削減は確認できたが、同じ魚雷本数帯での明確なcycle低減は観測できず、FPS効果を実証する情報はない。

## 限界

- jsonlにbuildフィールドがない。
- 有効なセッションはS2のみ。S1は旧meta混入で除外。
- ATMの有無はfilenameだけでは決まらず、記録からも実証不能（providerデータあり、producer未検証）。
- `isOwn`／`owner.isPlayer` が全行Noneのため、自艦全距離HIGH例外の実機確認はできていない。
- L3 counterfactualは分類tick現在全位置に限り、非分類tickの遠距離現位置は記録されていない。
- performance窓と魚雷本数の紐付けは、offset 24.922秒を使った近似対応に限り、厳密同期ではない。
- FPS・体感報告がないため、実際の体感への影響はunknown。
- 現行ソースは `0.3.41-team-torpedo-budget` だが、B48は `0.3.40-radius-l5` で取得された。0.3.41の敵20枠チーム予算はB48には適用されていない。

## 解析に使用したファイル

- `tools/analyze_b48_l5.py`：逐次jsonl解析スクリプト（匿名集計出力）。
- `tests/test_analyze_b48_l5.py`：dedup、weighted mean、nonfinite、session reset、距離分類、間隔、performance等のunit test。

private記録ファイルはGit管理しない。