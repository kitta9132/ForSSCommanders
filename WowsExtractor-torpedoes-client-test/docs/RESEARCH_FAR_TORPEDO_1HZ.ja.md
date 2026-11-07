# 遠距離魚雷の1Hz化：オフライン検証（未適用）

2026-11-07。遠距離（L/3超）だけを1Hzに落とす案が、行数・通信量・追従性の面で実装する価値があるかを、既存記録の再生と合成負荷で調べた。**ランタイムソースは変更していない。** 候補は`tools/`内のテスト専用サブクラスとして実装し、本番の`TorpedoSamplingGroups`、producer、viewer、wire契約には適用していない。ゲーム内試験も追加していない。

## 結論

現状のconsumer契約とviewerの持ち方をそのまま使う限り、**いま適用するほどの利点は確認できなかった**。

- サンプル行の削減はB43で**4.22%**、B44で**9.65%**。owner参照は**1.06%／3.88%**、試算バイト数は**1.99%／1.53%**減。効果はゼロではないが小さい。
- 遠距離の実測サンプル間隔は約1.02～1.10秒になり、既存`TorpedoMotion`の`0 < dt <= 1.0`契約を外れる。結果として遠距離の速度は**B43で80.5%、B44で95.2%**のサンプルでunknownになった。現行はどちらも0%。
- viewerは`group === 'low'`だけを1.5 game秒／1500 wall ms保持する。1Hzでは次サンプルまでの余裕が約0.5秒しかなく、負荷時に消える可能性がある。wireも`high`/`low`の二値前提で、`mid`追加は契約変更になる。
- したがって本稿の候補は**研究用の反実仮想**として残し、採用判断にはゲーム内のconsumer込み測定とmotion契約の再設計を別途必要とする。FPS改善率への換算は行わない。

## 候補仕様

| 距離 | グループ | 周期 |
| --- | --- | --- |
| `d <= min(mapWidth, mapHeight) / 5` | high | 0.2秒（5Hz） |
| `L/5 < d <= min(mapWidth, mapHeight) / 3` | mid | 0.5秒（2Hz） |
| `L/3 < d` | low | 1.0秒（1Hz） |

- 自艦所有（strict own `isPlayer is True`）は距離にかかわらずhigh。
- 新規、identity不明、距離不明、context lossは暫定high。
- 距離再分類は既存どおり5秒間隔。期限をまたぐcatch-upはせず、`now + interval`へ再アンカーする。
- 既存の列挙、identity読取り、membership、owner取得の順序は変えない。
- wireプロトタイプは`mid`サマリと`midRadiusWorld`を追加するが、**これは適用済み契約ではない**。

実装は`tools/far_torpedo_1hz_candidate.py`の`TieredTorpedoSamplingGroups`。本番クラスを継承し、`high/mid/low`の周期だけを差し替える。`CLASSIFICATION_INTERVAL = 5.0`、`HIGH_INTERVAL = 0.2`は維持する。

## 方法

1. **B43／B44の全位置記録を再生**。どちらも未サンプル記録で、毎tickの全魚雷位置がある。本番の`TorpedoTelemetry`、本番の`TorpedoMotion`、本番のwire圧縮をそのまま使った。baselineは現行sampler（L/5 high 5Hz、L/5超は平均2Hz）、candidateは上表。
2. baselineの再生成値が既存の公開済みB43／B44 budget（状態数、元行数、membership行数、sample行、high/low、position、owner、分類tick）と完全一致することを確認した。比較の土台としては再現性がある。
3. **B09は静的な分類tick幾何だけ**。B09は既にサンプル済みで、非分類tickの現在位置は記録されていない。欠測を過去位置や外挿で埋めず、完全リプレイとは呼ばない。分類tickの行だけを、自己位置と較正diagの地図短辺（欠ける場合は記録時の`radiusWorld × 3`）でL/5・L/3に分類した。
4. **合成216本／22 owner**を5反復×300tickで実行。安価な合成getterのホストPython 3計測であり、ゲーム時間でもFPSでもない。
5. private記録を使うテストは`WOWS_FAR_1HZ_REPLAY=1`のときだけ実行する。出力・本稿は匿名集計のみで、battle ID、owner ID、vehicle ID、weapon IDを出さない。

## B43／B44の実測

### サンプル行と費用

| 指標 | B43 baseline | B43 candidate | 差 | B44 baseline | B44 candidate | 差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 状態数 | 1,194 | 1,194 | 0 | 743 | 743 | 0 |
| 元の全魚雷行 | 95,413 | 95,413 | 0 | 9,671 | 9,671 | 0 |
| membership行 | 95,413 | 95,413 | 0 | 9,671 | 9,671 | 0 |
| サンプル行 | 73,711 | 70,598 | **-3,113（-4.22%）** | 6,044 | 5,461 | **-583（-9.65%）** |
| うちhigh | 59,145 | 59,145 | 0 | 3,640 | 3,640 | 0 |
| うちmid | 0 | 8,222 | +8,222 | 0 | 1,212 | +1,212 |
| うちlow | 14,566 | 3,231 | -11,335 | 2,404 | 609 | -1,795 |
| position読取り | 73,711 | 70,598 | -3,113 | 6,044 | 5,461 | -583 |
| owner参照 | 11,371 | 11,250 | **-121（-1.06%）** | 1,391 | 1,337 | **-54（-3.88%）** |
| identity読取り | 286,239 | 286,239 | 0 | 29,013 | 29,013 | 0 |
| 列挙回数 | 1,194 | 1,194 | 0 | 743 | 743 | 0 |
| 分類tick | 48 | 48 | 0 | 30 | 30 | 0 |
| 試算バイト数 | 126,684,130 | 124,158,594 | **-2,525,536（-1.99%）** | 26,170,810 | 25,770,946 | **-399,864（-1.53%）** |

- サンプル行とposition読取りは一致した。candidateでも`sampledByGroup`の合計はサンプル行と一致する。
- identity読取り、列挙回数、分類tick、membership行、near＋ownのサンプル行はbaselineとcandidateで同一。列挙・最小ID・membershipを削っていないことの確認になる。
- 試算バイト数は、元の状態にsamplerが返した行とstatusを差し替えてJSON化した大きさ。baselineの圧縮後と比較した比率で、元データ比ではない。通信路・submit・I/Oの固定費は含まない。
- owner参照は「1スナップショット×owner集合」の取得であり、魚雷行数に比例しない。合成でも22 ownerが全tierにまたがるため、owner参照は減らなかった。owner削減率を魚雷行削減率と同一視しない。

### 分類された距離帯

| 指標 | B43 baseline | B43 candidate | B44 baseline | B44 candidate |
| --- | ---: | ---: | ---: | ---: |
| near | 1,861 | 1,861 | 122 | 122 |
| mid（L/5～L/3） | 0 | 859 | 0 | 129 |
| far（L/3超） | 1,559 | 700 | 256 | 127 |
| unknown distance | 369 | 369 | 0 | 0 |
| classified | 3,789 | 3,789 | 378 | 378 |
| new | 20 | 20 | 3 | 3 |
| group change | 284 | 383 | 45 | 67 |
| provisional high | 20 | 20 | 3 | 3 |
| pruned | 8 | 8 | 0 | 0 |

分類tick上の`far`が減り、その分が`mid`へ移る。near、unknown、new、provisional high、prunedは変わらない。group changeが増えるのは、candidateがL/5～L/3を`mid`として独立に扱い、baselineでは`low`のままだったL/3跨ぎをグループ変更として数えるため。距離の計算式そのものは変えていない。

### サンプル間隔とmotion

`TorpedoMotion`は`0 < dt <= 1.0`だけを受け付け、1.0秒を超えると履歴をリセットする。実tickは約0.204秒間隔なので、1Hzの遠距離サンプルは位相により約1.02～1.10秒になる。

| 指標 | B43 baseline | B43 candidate | B44 baseline | B44 candidate |
| --- | ---: | ---: | ---: | ---: |
| 遠距離サンプル間隔の数 | 6,936 | 3,823 | 1,192 | 609 |
| うち1.0秒超 | 0 | **3,079（80.5%）** | 0 | **580（95.2%）** |
| 遠距離間隔の中央値 | 0.424秒 | 1.028秒 | 0.419秒 | 1.023秒 |
| 遠距離間隔の最大 | 0.680秒 | 1.098秒 | 0.628秒 | 1.036秒 |
| 遠距離で速度available | 6,936 | 744 | 1,192 | 29 |
| 遠距離で`gapOverOneSecond` | 0 | 3,079 | 0 | 580 |
| 全体の速度unknown | 350 | 3,437 | 64 | 647 |

- 全体の速度unknownの増分はB43で+3,087、B44で+583。baselineのunknownは初回観測のみ。
- mid（0.5秒）でも実記録では8件（B43）／3件（B44）が1.0秒を超えた。0.5秒周期の量子化だけでは説明できず、処理遅延・tick揺らぎの影響を含む。
- 合成ベンチマークは正確な0.2秒tickなので遠距離1Hzでも`dt = 1.0`になり、速度unknownは増えない。**合成のmotion結果を実記録の代用にしない。**
- 1Hz化の可否は「遠距離の速度を捨ててよいか」にほぼ集約される。速度が必要なら、far用に許容`dt`を広げる、1Hzサンプルから速度を出さない、別の推定を使う、のいずれかの設計変更が先に必要。

## B09の静的幾何（リプレイではない）

B09は既にサンプル済みのため、分類tickの現在位置だけを使った。非分類tickの欠測は復元していない。L/5とL/3の境界は、自己位置と較正diagの地図短辺から計算した。

| 指標 | セッションA | セッションB |
| --- | ---: | ---: |
| 状態数 | 919 | 677 |
| 全detail行 | 16,904 | 13,844 |
| 分類tick | 37 | 28 |
| うち魚雷0のtick | 18 | 16 |
| 分類に使えたtick | 37 | 28 |
| 採用行 | 729 | 613 |
| near（L/5以内） | 324 | 248 |
| mid（L/5～L/3） | 292 | 264 |
| far（L/3超） | 113 | 101 |
| unknown distance | 0 | 0 |
| far比率 | **15.50%** | **16.48%** |
| 同時刻の最大行数 | 87 | 87 |
| 条件不足でskipしたtick | 0 | 0 |

- farは分類tick行の15～16%で、B43／B44より遠距離の比重が小さい。ただしこれは分類tickだけの静的な幾何であり、5秒枠、新規high、due期限、移動・消失を再生した削減率ではない。
- 全detail行に対する削減率へ外挿しない。分類tick以外の行は、その時点の帯が分からない。

## 合成216本／22 ownerのホスト計測

5反復×300tick、合計1,500tick。魚雷216本（near 72、mid 72、far 72、own 54）を固定配置し、合成getterで計測した。

| 指標 | baseline | candidate | 差 |
| --- | ---: | ---: | ---: |
| サンプル行 | 234,900 | 220,050 | **-14,850（-6.32%）** |
| high | 175,500 | 175,500 | 0 |
| mid | 0 | 29,700 | +29,700 |
| low | 59,400 | 14,850 | -44,550 |
| position読取り | 234,900 | 220,050 | -14,850 |
| identity読取り | 972,000 | 972,000 | 0 |
| owner参照 | 33,000 | 33,000 | 0 |
| 列挙回数 | 1,500 | 1,500 | 0 |
| 速度unknown | 1,080 | 1,080 | 0 |
| 中央値（ms/tick） | 5.72 | 5.65 | -1.2% |

- これは**ホストPython 3＋安価な合成getter**の数値で、ゲーム時間でもFPSでもない。実ゲームの改善率として引用しない。
- 同日の別実行では中央値が6.40→5.60 msだった。実行間のばらつきが大きく、時間差は判断材料にしない。行数・読取り回数だけを比較材料にする。
- 速度unknownが増えないのは、tickが正確に0.2秒で、遠距離がちょうど1.0秒間隔になるため。実記録のjitterを再現していない。

## consumer・wire・UIのリスク（静的調査、未計測）

以下はMiMoの独立静的調査から得たリスクで、**本実験ではゲーム内挙動を測っていない**。実測結果と区別して扱う。

1. **`TorpedoMotion`の`0 < dt <= 1.0`契約**：>1.0秒で履歴をリセットする。1Hz＋jitterでは遠距離の速度が欠落する。これは本実験で実測済み（上表）。契約を変えるなら、far用の許容幅、または速度を出さない設計を明示する必要がある。
2. **viewerの保持は`group === 'low'`のみ**：保持期間は1.5 game秒／1500 wall ms。1Hzでは次サンプルまで約1.02秒で、wall timeの余裕は約0.5秒。負荷でサンプル間隔が1.5秒を超えると、前回表示が消える可能性がある。現行2Hzは約0.42秒間隔で余裕が大きい。UIでの実測は未実施。
3. **wire契約が`high`/`low`の二値前提**：`mid`サマリと`midRadiusWorld`の追加はproducer・consumer双方の契約変更。プロトタイプの`tiered_sampling_wire_payload`は適用していない。旧consumerが`mid`を未知グループとしてどう扱うかは未計測。
4. **UIの同一sample joinとsubset抑止**：viewerはmembership内の同一identityが1件のときだけlowを保持する。candidateでは遠距離のsample行が減るため、同じtickにUIが参照できる行の集合が変わる。farの1Hz gridとUIのprobe gridのずれが、保持・選択・表示に与える影響は未計測。baseline 2Hzと比較してcandidateが悪化するかも不明。
5. **far→nearの5秒再分類遅延**：既存仕様であり、候補で新たに発生するものではない。ただし1Hz化で観測密度が下がるため、境界を跨いだ魚雷がnearへ昇格するまでの見え方は粗くなる。遅延の実測はしていない。new／unknown／context lossの暫定highと自艦strict own highは維持する。
6. **`docs/FPS_TASKS.ja.md`の旧毎tick案**：現在の仕様根拠に使わない。本次候補はL/5 high 5Hz、L/5～L/3 mid 2Hz、L/3超 low 1Hzの三段であり、毎tick案とは異なる。

## 判断

**今回は採用しない。** 理由は、削減が小さい一方で、遠距離の速度欠落、viewerの保持余裕、wire契約変更というconsumer側のコストが大きいため。特にmotionの速度unknown 80～95%は、ゲーム内でそのまま体験品質の低下になり得る。

再検討の条件は次のとおり。

- 遠距離の速度を不要とする、またはfar用のmotion許容`dt`・推定方式を先に設計して検証する。
- viewerの保持TTLと`mid`グループの扱いを契約として更新し、負荷時の消え方を測る。
- wireの`mid`追加を含むproducer／consumerの互換性を確認する。
- ゲーム内で、魚雷表示の追従、UIの選択、owner参照、通信量を測る。ホスト計測の時間差は使わない。
- 遠距離の鮮度1Hzを許容できるか、product判断を先に決める。

代替として、現行2Hzを維持したままwire圧縮やowner参照の固定費を減らす方が、consumer契約を変えずに済む。今回の測定だけでは、1Hz化のために契約変更を行う根拠は得られなかった。

## 制約

- B43／B44はATMなしの特定セッションで、全魚雷位置がある未サンプル記録。B09はATMあり・L/3時代の既サンプル記録で、静的分類tickのみ。
- baselineの再現一致は確認したが、candidateのゲーム内周期・FPS・通信路の実費用は未計測。
- バイト数はJSON化した試算で、submitやI/Oを含まない。サンプル行削減とFPS削減を同比例換算しない。
- owner参照はスナップショット単位であり、行数削減と比例しない。
- 合成は正確な0.2秒tick・安価なgetterで、実記録のjitterや実ゲームのコストを再現しない。
- B09の分類tick幾何を全tickの削減率へ外挿しない。

## 再現コマンド

```powershell
cd WowsExtractor-torpedoes-client-test
python tools/compare_far_torpedo_1hz.py `
  --recording recordings/without-atm-b43.jsonl `
  --recording recordings/without-atm-b44.jsonl `
  --b09 recordings/with-atm-b09.jsonl `
  --synthetic --repeats 5 --ticks 300 `
  --json-output "$env:TEMP\far1hz.json"
```

```powershell
python -m pytest tests/test_far_torpedo_1hz_research.py -q
$env:WOWS_FAR_1HZ_REPLAY='1'
python -m pytest tests/test_far_torpedo_1hz_research.py -q
```

通常テストは8件、private再生テストは環境変数指定時に2件（B43／B44）。既存の`test_torpedo_sampling_groups.py`、`test_torpedo_sampling_integration.py`、`test_torpedo_high_load_budget.py`、`test_torpedo_telemetry.py`も合わせて実行し、失敗がないことを確認した。

## 追加・変更したファイル

- `tools/far_torpedo_1hz_candidate.py`：テスト専用の三段samplerとwireプロトタイプ。
- `tools/compare_far_torpedo_1hz.py`：B43／B44再生、B09静的幾何、合成ベンチマーク。
- `tests/test_far_torpedo_1hz_research.py`：境界、周期、own昇格、new／unknown／context loss、再分類、identity型、wire契約、実motion、合成、private再生の検証。
- 本稿。

`res_mods/`以下のランタイムソース、installer、viewer、記録、`.gitignore`、`.ai`の追跡変更は行っていない。commit／pushもしていない。