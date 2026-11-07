# B49 チーム魚雷予算解析（0.3.42-launch-restricted-builtins）

**訂正：以前の資料に「B49無効」と記載されていたが、それは 0.3.41 起動試行のみの話である。**
`recordings/without-atm-b49.jsonl` はその後の 0.3.42-launch-restricted-builtins 起動で**有効に記録されており**、
**1 meta + 1,058 state = 1,059 records、SHA256 `991c37056d63cade3766282ab714d67aa5627a484f30ff1e53a0a9015902b00e`**、
ファイルサイズ 185,309,892 byte である。最終フレームは `active: false` の正常終了形。

解析は匿名集計のみで、battle ID・player ID・vehicle ID・weapon ID・生ログ・ファイルパスは公開しない。

## 記録の健全性

| 項目 | 値 |
| --- | ---: |
| ファイルサイズ | 185,309,892 byte |
| SHA256 | `991c37056d63cade3766282ab714d67aa5627a484f30ff1e53a0a9015902b00e` |
| 総records | 1,059（meta 1 / state 1,058） |
| 壊損JSON行 | 0 |
| 空行 | 0 |
| 最終フレーム | state / active=false（正常終了） |
| セッション数 | 1（S1） |
| active state数 | 1,057（inactive 1） |
| 期間 | 約217.4秒 |

全行 `json.loads` 成功。`Stop-Process` による終了 code 1 でも書き込みは flush され、JSON 構造は最終行まで有効。

## 試験条件

| 項目 | 値 |
| --- | --- |
| modバージョン | `0.3.42-launch-restricted-builtins` |
| 採用ポリシー | `0.3.41-team-torpedo-budget` |
| 半径 | L/5（`min(mapWidth,mapHeight)/5.0`） |
| 敵HIGH予算 | 20本 |
| allyLow | True（設定値） |
| マップ | IDS_SPACES/00_CO_OCEAN |
| モード | GAMEMODE_AWESOME / TrainingBattle / 12対12 |
| roster | 24隻（Destroyer 23 / Cruiser 1） |
| 自艦 | Minotaur |
| 相手艦種 | Chateaurenault ×23 |
| ユーザー報告艦数 | 11v12（シャトルーノー） |

rosterは12対12だが、ユーザー報告は11v12。実動艦数は推測せず、両方を記載する。

## 半径・距離条件

| 項目 | 実測値 |
| --- | ---: |
| radiusWorld | 239.993 |
| 較正地図短辺 L | 1,199.965 |
| L / radiusWorld | **5.0** |
| mapSource | `calibratedMapExtents` |
| mapInferred | `True` |
| teamPolicy.radiusDivisor | 5.0（全1,057 state） |
| teamPolicy.enemyHighLimit | 20（全1,057 state） |

## 魚雷本数：延べ・同時最大・ユニーク

| 指標 | S1 |
| --- | ---: |
| membership延べ行 | 93,302 |
| detail sample延べ行 | 89,546 |
| 最大同時membership | **240** |
| 最大同時detail | 240 |
| 最大owner数（1 stateあたり） | 23 |
| ユニークidentity | 303 |
| ユニックowner | 23 |
| 初回魚雷出現 | meta開始後 **100.7秒**（membership 4 / detail 4） |

## グループ別サンプリング

| 指標 | S1 |
| --- | ---: |
| HIGH member / sampled | 86,888 / 86,888（省略0） |
| LOW member / sampled | 6,414 / 2,658 |
| LOW省略率 | **58.6%** |
| 全membershipに対するdetail比率 | **95.9%** |
| HIGH member割合 | 93.1% |
| LOW member割合 | 6.9% |

B48（0.3.40 L/5、team予算なし）ではHIGH member割合47.5%、detail比率69.3%であった。B49ではteam予算によりほとんどの行がHIGHとして扱われ、結果的にdetail比率が高い。ただしこれは「改善」ではなく、safety HIGH（主に `unknownTeamHigh` と、自艦context欠減に伴う `unknownDistanceHigh`）が多いため。

## 距離分類tickの幾何

分類tick（`classification.ts == state.ts`）で現在全positionsを比較。analyzerは各行の `position` と `self.position` から水平距離を再計算する。wire上の `sampling.distanceSquared` / `sampling.distanceStatus` は本記録では記録されていないため、幾何比較は生world positionに依存する。

| 指標 | S1 |
| --- | ---: |
| 分類tick総数 | 43 |
| 利用可能tick | 42 |
| skip tick | 1（contextMissing、行数0） |
| 分類tick行数合計 | 3,795 |
| `self.position` 欠減tick | 12 / 43 |
| `self.position` ありの行数 | 1,377 |
| `self.position` 欠減によるunknown行 | 2,418 |
| L5 near（d ≤ L/5） | 584（15.4% / 全分類tick行） |
| L5 mid（L/5 < d ≤ L/3） | 788（20.8%） |
| L5 far（d > L/3） | 5（0.1%） |
| L5 unknown距離 | 2,418（**63.7%**） |
| L3 near（d ≤ L/3） | 1,372（36.2%） |
| L3 far | 5（0.1%） |

### self position ありの「真のL5幾何」

`self.position` が取得できた 1,377 行に限定すると、幾何的なL5分類は以下の通り。**このサブセットでの L5 near は 42.4%** と、B48 の 43.6% と同じ範囲内である。

| 指標 | self position あり 1,377行 |
| --- | ---: |
| L5 near（d ≤ L/5） | 584（**42.4%**） |
| L5 mid（L/5 < d ≤ L/3） | 788（57.2%） |
| L5 far（d > L/3） | 5（0.4%） |
| L3 near（d ≤ L/3） | 1,372（99.6%） |
| L3 far | 5（0.4%） |

| 同一分類tickの実HIGH／LOW | 値 |
| --- | ---: |
| 実HIGH member / sampled | 3,544 / 3,544 |
| うち L5 near | 475 |
| うち L5 mid（非near HIGH） | 646 |
| うち L5 unknown距離 | 2,418 |
| 実LOW member / sampled | 251 / 251 |
| うち L5 mid | 142 |
| うち L5 near | 109 |
| LOW far | 0 |

**解釈**：分類tick全体での L5 near 15.4% は、**12/43 の分類tickで `self.position`（＝sourceの分類context selfPosition）が欠減したため、2,418行が unknown になったことで低く見える**。魚雷rowのworld positionは 89,546行すべて取得できている。`self.position` ありの行では L5 near 42.4% と B48 の 43.6% は近似しており、「team予算導入で幾何的near率が下がった」とは断定できない。

## teamPolicy の実動作

`torpedoStatus.sampling.teamPolicy` は全1,057 active stateで存在した。

| カウンタ | min | median | max | 備考 |
| --- | ---: | ---: | ---: | --- |
| ownHigh | 0 | 0 | 0 | 自艦検出なし（`isPlayer=True` 未観測） |
| allyLow | 0 | 0 | 0 | 確定味方（`isPlayer=False` 同team）検出なし |
| enemyHigh | 0 | 0 | 20 | 敵20枠予算が発動 |
| enemyLow | 0 | 0 | 62 | 遠距離／予算外の敵 |
| safetyHigh | 0 | 58 | 240 | 安全側HIGH合計 |
| unknownTeamHigh | 0 | 58 | 158 | `allyUnknown`（同teamだが `isPlayer` 判定不能）と `unknown`（teamも判定不能）の合計 |
| unknownDistanceHigh | 0 | 0 | 82 | 敵だが分類context（主に `selfPosition`）欠減で距離unknown |

| 検証項目 | 結果 |
| --- | --- |
| enemyHigh > 20 となった state | **0**（予算超過なし） |
| enemyHigh > 0 となった state | 186 |
| enemyHigh == 20（上限到達）の state | 126 |
| 初回 enemyHigh > 0 | meta開始後 **113.3秒** |
| total high > 20 となった state | **561** |
| source/revision フィールドの観測 | なし（wireには含まれない） |

### 解釈

- **敵20枠予算は機能した**：enemyHigh は常に 20 以下で、上限到達は 126 state 観測された。
- **確定 allyLow は 0**：`owner.isPlayer` が `False` として観測された味方魚雷は存在しなかった。したがって allyLow の 2Hz 緩和は本記録では実質的に発動していない。
- **unknownTeamHigh は最大158本**：`unknownTeamHigh` は source の `_team_counts` で `allyUnknown`（同teamだが `isPlayer` 判定不能）と `unknown`（teamも判定不能）の両方を集計している。したがって「すべて同teamの安全HIGH」と断定できない。B48と同様に `owner.isPlayer` は全行 `None` のため、own/ally/unknown の内訳は記録から分離できない。
- **unknownDistanceHigh の発生要因**：source の `_sampling_distance` は分類context（`selfPosition` + 地図較正）がない場合に距離を `unknown` とする。本記録では 43 分類tick中 12 tick で `self.position` が欠減しており、その影響で `unknownDistanceHigh` が最大82本に達した。魚雷rowのworld positionはすべて取得できているため、これは魚雷位置欠減ではなく自艦context欠減による分類skipである。
- **total high > 20 の理由**：safetyHigh（unknownTeamHigh + unknownDistanceHigh）は敵20枠予算にカウントされないため、total HIGH member は最大240本まで膨らんだ。これは設計どおりの動作。
- **source/revision**：state wire の teamPolicy には含まれない。TTaro Mod Config パネル経由で source/revision が取得できたかどうかは、本記録では未検証。

## own 全距離例外と row-level teamClass/reason

| 項目 | 値 |
| --- | --- |
| `isOwn == True` | 0 / 89,546 detail行 |
| `isOwn == None` | 89,546 / 89,546 |
| `owner.isPlayer == True` | 0 |
| `owner.isPlayer == None` | 89,546 |
| row-level `teamClass` | **未公開**（wireに含まれず） |
| row-level `sampling.reason` | **未公開**（全行 `notPublished`） |

B48と同じく、本記録では `isPlayer=True` の strict own 検出は一切ない。したがって「自艦ownは全距離HIGH」の実機動作確認は本記録からはできない。

## 連続identity sample間隔

| グループ | n | min | p10 | median | mean | p90 | p95 | max | >1s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HIGH | 86,649 | 0.200 | 0.201 | **0.207** | 0.207 | 0.212 | 0.214 | 0.639 | 0 |
| LOW | 2,594 | 0.201 | 0.409 | 0.426 | **0.503** | 0.628 | 0.630 | 0.645 | 0 |
| 全体 | 89,243 | 0.200 | 0.201 | 0.207 | 0.216 | 0.213 | 0.216 | 0.645 | 0 |

HIGHは約5Hz、LOWは **mean 0.503 s（≈1.99 Hz）** で安定。median 0.426 s の逆数を周波数として用いない。1秒超のgapなし。B48（LOW mean 0.502 s）と同水準。

## 位置欠測とmotion availability

| 項目 | 値 |
| --- | --- |
| world position欠測 | 0 / 89,546 |
| `self.position` 欠測 classification tick | 12 / 43（B49 調査結果、2,418 行が unknown 距離） |
| `self.position` 欠測 active state | **287 / 1,057 active state（27.2%）** |
| mapPositionStatus unknown | 7,279（HIGHのみ、8.1%） |
| motion unavailable | 303（high 239 / low 64） |
| speed missing | 0 |

**訂正・補足**：表の「`self.position` 欠測state」は分類 tick 数の誤記だった。実際には active state 全体で 287/1,057（27.2%）で `self.position` が欠測しており、これは自艦沈没後（ts ≈ 403 s 以降）に集中している。詳細は `docs/RESEARCH_B49_CLASSIFICATION_GAPS.ja.md` を参照。

`speedMissing: 0` は `motionUnavailable: 303` と整合している。`speedMissing` は `motion.available == True` の行で `horizontalSpeed` が finite でない場合のみカウントする。`motion.available != True` の行では速度フィールドを読まないため、speed missing としてはカウントされない。

## performance：5秒窓加重平均

| phase | 加重平均ms | totalCount | 単発max | 窓平均median | 窓平均p95 | 窓平均max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| state_cycle_total | 16.448 | 1,042 | 47.039 | 13.886 | 29.958 | 33.007 |
| snapshot_build_total | 13.091 | 1,042 | 38.486 | 11.065 | 23.286 | 25.818 |
| avatar | 4.123 | 1,042 | 14.659 | 4.078 | 4.537 | 5.155 |
| ships | 1.548 | 1,042 | 3.749 | 1.596 | 1.865 | 1.927 |
| torpedoes | 5.347 | 1,042 | 25.353 | 3.017 | 14.929 | 16.183 |
| submit | 3.326 | 1,042 | 11.659 | 2.791 | 6.558 | 7.145 |
| gun_sampling | 0.728 | 1,042 | 1.704 | 0.715 | 0.805 | 0.842 |
| self | 0.714 | 1,043 | 1.788 | 0.712 | 0.758 | 0.795 |
| armament_systems | 0.186 | 1,042 | 0.539 | 0.248 | 0.265 | 0.272 |
| submarine_sampling | 0.142 | 1,042 | 0.465 | 0.143 | 0.163 | 0.184 |

42窓中19窓はmembership 0、23窓が正のmembership。最もcycle平均が重かった1窓（membership 240、5.001秒）：

| phase | 平均ms | 単発max | count |
| --- | ---: | ---: | ---: |
| state_cycle_total | 33.007 | 47.039 | 24 |
| snapshot_build_total | 25.818 | 38.486 | 24 |
| torpedoes | 16.183 | 25.353 | 24 |

## 魚雷本数帯別の近似比較

state.ts と performance sampleEndSeconds の offset は 20.60–20.81秒（median 20.62秒）。以下はこのoffsetを使った近似対応。

| 帯（membership） | 窓数 | 平均membership | cycle平均ms | torpedoes平均ms |
| --- | ---: | ---: | ---: | ---: |
| 0 | 19 | 0 | 8.882 | 0.115 |
| 1–49 | 2 | 37.5 | 11.671 | 1.443 |
| 50–99 | 2 | 67.5 | 14.965 | 3.862 |
| 100–179 | 6 | 144.8 | 21.362 | 8.605 |
| 180+ | 13 | 208.3 | 26.415 | 12.484 |
| 正のmembership | 23 | 164.7 | 22.786 | 9.731 |

## B48 L/5（0.3.40）との比較

| 指標 | B48 S2（0.3.40 L/5） | B49 S1（0.3.42 team予算） |
| --- | ---: | ---: |
| modバージョン | 0.3.40-radius-l5 | 0.3.42-launch-restricted-builtins |
| 採用ポリシー | 距離のみ L/5 | 0.3.41-team-torpedo-budget |
| 期間 | 約185.1秒 | 約217.4秒 |
| 最大membership | 280 | 240 |
| membership延べ | 67,970 | 93,302 |
| detail延べ | 47,135 | 89,546 |
| detail/membership比率 | 69.3% | **95.9%** |
| HIGH member割合 | 47.5% | **93.1%** |
| 全membership省略率 | 30.7% | **4.0%** |
| LOW省略率 | 58.4% | 58.6% |
| L5 near（分類tick、全行） | 43.6% | 15.4% |
| L5 near（分類tick、`self.position` あり） | — | **42.4%** |
| L5 unknown距離（分類tick） | 0% | **63.7%** |
| cycle加重平均ms | 14.284 | 16.448 |
| 最重窓cycle平均ms | 25.273 | 33.007 |
| 単発cycle max ms | 39.513 | 47.039 |
| LOW mean間隔 | 0.502s | 0.503s |
| LOW median間隔 | 0.429s | 0.426s |
| own.isPlayer | 全None | 全None |
| owner.isPlayer | 全None | 全None |

**構成差・解釈差**：

- B49の期間はB48より約32秒長い。
- B49ではteam予算により多くの行がHIGH（主にsafetyHigh）に分類されたため、detail比率が高く、省略率が低く見える。これを「性能改善」とは扱わない。
- 分類tick全体の L5 near 15.4% は、12/43 の分類tickで `self.position`（sourceの分類context）が欠減したために unknown が63.7%となったため、`self.position` ありの行に限定した真のL5幾何（42.4%）と混同しない。42.4% は B48 の 43.6% と同じ範囲内であり、team予算導入で幾何的near率が下がったとは断定できない。
- cycle加重平均はB48より重いが、max membership 240 vs 280、期間、艦の動き等が異なる。因果的な改善率とは扱わない。
- `isPlayer` が全行 `None` のため、味方2Hz（allyLow）は本記録では実質的に機能していない。

## python.log 確認（匿名要約）

`recordings/deployment-0.3.42-b49/python.log` を確認した。

| 時刻（JST） | 内容 |
| --- | --- |
| 10:47:31 付近 | WowsExtractor 0.3.41 起動試行 → `NameError: global name 'globals' is not defined` で失敗 |
| 10:50:44 付近 | 同じく WowsExtractor 起動試行 → 同じ `globals` NameError で失敗 |
| 10:48/10:50/10:59 | `UserDataGate` Invalid data エラー多数（戦闘ロビー/チャット周り） |
| **11:36:22** | **WowsExtractor `loaded v0.3.42-launch-restricted-builtins`（成功）** |
| 11:36:21 | TTaroModUtils schema スキャン：INFO レベルの `no migrationVersion`（通常動作） |
| **11:40:11** | **WowsExtractor telemetry 書き込み開始、`meta.json written (24 players, ready=True)`** |
| 11:40:11 以降 | WowsExtractor / UserDataGate / collector エラーは確認されず、TTaro 系は INFO のみ |

したがって、B49 記録は **11:36:22 の 0.3.42 成功ロード以降に取得された有効な記録**である。10:47/10:50 の失敗は .41 試行分であり、B49 全体を「無効」とするのは誤り。

## どこが確認できたか

1. **0.3.42 の記録は有効**：1,059 records、全行 JSON 有効、最終フレーム active=false、SHA256 一致。
2. **team-torpedo-budget ポリシーが動作**：`0.3.41-team-torpedo-budget` が全 active state で報告された。
3. **敵20枠予算が発動**：enemyHigh は 0–20 の範囲で、20 に達した state が 126 回、超過は 0。
4. **L/5 半径は維持**：radiusDivisor 5.0、radiusWorld 239.993。
5. **HIGH/LOW cadence は維持**：HIGH 約5Hz、LOW mean 0.503 s（≈1.99 Hz）、1秒超gapなし。
6. **own/ally strict 判定は未観測**：`isOwn`/`owner.isPlayer` は全行 `None` のため、味方2Hzの効果は本記録では確認できない。
7. **safety HIGH が大半**：unknown team/distance により total HIGH が 20 を大きく超えた（最大240本）。ただし `unknownTeamHigh` の内訳（`allyUnknown` vs `unknown`）は記録から分離できない。
8. **unknownDistance は主に自艦context欠減**：12/43 の分類tickで `self.position` が欠減し、2,418行が unknown 距離となった。魚雷rowのworld positionはすべて取得できている。
9. **.42 成功後はエラーなし**：11:36:22 以降、WowsExtractor/collector/TTaro/schema において ERROR は確認されなかった。

## 限界・未確定

- `owner.isPlayer` が全行 `None` のため、自艦全距離HIGH例外・確定allyLowの実機確認はできていない。
- `unknownTeamHigh` は source で `allyUnknown` と `unknown` の合計であり、すべて同teamとは断定できない。
- row-level の `teamClass`・`sampling.reason` は wire から strip されており、記録には存在しない。
- row-level の `sampling.distanceSquared`・`sampling.distanceStatus` は本記録では wire に含まれていない。幾何比較は analyzer が world position から再計算したものに限る。
- `teamPolicy.source` / `revision` は state wire に含まれない。TTaro Mod Config パネルでのリアルタイム操作と値取得は未検証。
- performance 窓と魚雷本数の紐付けは、state.ts と sampleEndSeconds の offset（約20.62秒）を使った近似に限る。
- FPS min22 はユーザー体感報告であり、profiler クロックとの同期は不明。
- B48とB49は試験長、魚雷ありなしの割合、艦の動き等が異なるため、数値の単純な因果比較はできない。
- 11v12 というユーザー報告と roster 12対12 の差は解決していない。

## 使用ファイル

- `tools/analyze_b49_team_budget.py`：B49 専用匿名集計解析スクリプト（teamPolicy 対応）。
- `tests/test_analyze_b49_team_budget.py`：teamPolicy、JSON 健全性、terminal frame、anonymity の unit test。
- `recordings/without-atm-b49.jsonl`：private 記録（Git 管理外）。
- `recordings/deployment-0.3.42-b49/python.log`：private ゲームログ（Git 管理外）。
