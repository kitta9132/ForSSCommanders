# 近距離魚雷HIGH枠の上限25本：オフライン検証（未適用）

2026-11-07。**研究時のbaselineである0.3.40のL/5距離制サンプラー**（L/5以内はhigh 5Hz、L/5外は平均2Hz low）を対象に、**非自艦かつL/5内でknown距離の魚雷を距離順に最大25本だけhigh 5Hz**へ絞る案を、既存記録の再生と合成負荷で調べた。**ランタイムソースは変更していない。** 候補は`tools/`内のテスト専用サブクラスとして実装し、本番の`TorpedoSamplingGroups`、producer、viewer、wire契約には適用していない。ゲーム内試験もrecorder操作も追加していない。

> 補足（2026-11-07）：後続の`0.3.41-team-torpedo-budget`でproduction側にチーム別分類と敵near予算（既定**20**）を実装した。本稿の上限**25**は研究用の反実仮想のままで、production既定ではない。また0.3.41は初観測でも分類するため、本稿の「初回分類は全行が`new`で安全側high」という上限例外はlegacy baseline（`LegacyTorpedoSamplingGroups`）の挙動である。詳細は[チーム別魚雷サンプリング](TEAM_TORPEDO_BUDGET.ja.md)を参照。

## 結論

**B43では効果があり、B44では効果がない。** 採否は「近距離の同時多発時に上位25本だけ5Hzで足りるか」というproduct判断に依存する。研究用の反実仮想として残し、今回は採用しない。

- 25本超過は**B43で実際に発生**した（48分類tick中25tick、のべ超過1,224本）。candidateはサンプル行を**-24.24%**、high行を**-50.4%**、試算バイト数を**-12.22%**削減した。owner参照は**-19.7%**。
- **B44は分類tickで25本を超えず**、capの効果はゼロ（サンプル行・バイト数ともbaselineと同一）。
- 上限25は**瞬時上限ではない**。初回分類は全行が`new`で安全側highになるため、B43では最大**185本**が一時的にhighになる（上限例外）。steady状態の平均上限として働く。
- 既存far 1Hz候補と違い、swing行は**平均2Hz（0.5秒）**を維持する。速度unknownは増えず、`dt > 1.0`は**0件**。速度欠落という代償は発生しない。
- 距離順は**脅威順位ではない**。CPA・誘導先推定は本稿のscope外。

## 候補仕様

| 条件 | グループ | 周期 |
| --- | --- | --- |
| 非自艦・known距離・`d <= min(mapWidth, mapHeight)/5`・再分類済み・距離順で上位25本 | high | 0.2秒（5Hz） |
| 上記のL/5内で26位以下 | low | 0.5秒（2Hz・平均） |
| `d > L/5` | low | 0.5秒（2Hz・平均） |

- 自艦所有（strict own `isPlayer is True`）は距離にかかわらずhigh。**25枠の判定にownは数えない。**
- `new`、距離不明、識別不明（unknown／duplicate）、context lossは既存の安全側high。これらは**cap例外**であり、**総high本数は25で縛られない**。
- 距離再分類は既存どおり**5秒間隔**。期限をまたぐcatch-upはせず`now + interval`へ再アンカーする。既存のnear移籍5秒遅延はそのまま維持し、ヒステリシスは追加しない。
- 同距離のtieは**距離のみの安定ソート**で解決する（列挙順を保持し、strictなidentity値比較は行わない）。
- 既存の列挙、identity読取り、membership、owner取得の順序は変えない。
- wireは本番`sampling_wire_payload`（`high`/`low`のみ）をそのまま使う。cap metadataは**adapter-localのclassificationに追加**し、**wireには出さない**（cap表現は今後の研究課題）。

実装は`tools/torpedo_high_budget_25_candidate.py`の`CapTorpedoSamplingGroups`。本番`TorpedoSamplingGroups`を継承し、`_observe_classification`だけを上書きする。cadence、own昇格、newフォールバック、`CLASSIFICATION_INTERVAL = 5.0`、`HIGH_INTERVAL = 0.2`は基底を継承する。

## 方法

1. **B43／B44の全位置記録を再生**。どちらも未サンプル記録で、毎tickの全魚雷位置がある。本番の`TorpedoTelemetry`、本番の`TorpedoMotion`、本番のwire圧縮をそのまま使った。baselineは現行sampler、candidateは上表。
2. baselineの再生成値が既存の公開済みB43／B44 budget（状態数、元行数、membership行数、sample行、high/low、position、owner、分類tick）と一致することを確認した。
3. **B09は静的な分類tick幾何だけ**。B09は既にサンプル済みで、非分類tickの現在位置は記録されていない。欠測を過去位置や外挿で埋めず、完全5秒replayとは呼ばない。分類tickの行だけを、自己位置と較正diagの地図短辺（欠ける場合は記録時の`radiusWorld × 3`、0.3.38のL/3記録）でL/5分類した。
4. **合成216本／22 owner**を5反復×300tickで実行。allNear／halfNear／ownMixedの3配置。cap選別コスト（距離ソート）を含む。安価な合成getterのホストPython 3計測であり、**ゲーム時間でもFPSでもない**。
5. private記録を使うテストは`WOWS_HIGH_BUDGET_25_REPLAY=1`のときだけ実行する。出力・本稿は**匿名集計のみ**で、battle ID、owner ID、vehicle ID、weapon IDを出さない。

## B43／B44の実測

### サンプル行と費用

| 指標 | B43 baseline | B43 candidate | 差 | B44 baseline | B44 candidate | 差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 状態数 | 1,194 | 1,194 | 0 | 743 | 743 | 0 |
| 元の全魚雷行 | 95,413 | 95,413 | 0 | 9,671 | 9,671 | 0 |
| membership行 | 95,413 | 95,413 | 0 | 9,671 | 9,671 | 0 |
| サンプル行 | 73,711 | 55,841 | **-17,870（-24.24%）** | 6,044 | 6,044 | **0** |
| うちhigh | 59,145 | 29,339 | **-29,806（-50.4%）** | 3,640 | 3,640 | 0 |
| うちlow | 14,566 | 26,502 | +11,936（+81.9%） | 2,404 | 2,404 | 0 |
| position読取り | 73,711 | 55,841 | -17,870 | 6,044 | 6,044 | 0 |
| owner参照 | 11,371 | 9,132 | **-2,239（-19.69%）** | 1,391 | 1,391 | 0 |
| identity読取り | 286,239 | 286,239 | 0 | 29,013 | 29,013 | 0 |
| 列挙回数 | 1,194 | 1,194 | 0 | 743 | 743 | 0 |
| 分類tick | 48 | 48 | 0 | 30 | 30 | 0 |
| 試算バイト数 | 126,684,130 | 111,203,040 | **-15,481,090（-12.22%）** | 26,170,810 | 26,170,810 | **0** |

- サンプル行とposition読取りは一致した。`sampledByGroup`の合計はサンプル行と一致する。
- identity読取り、列挙回数、分類tick、membership行はbaselineとcandidateで同一。列挙・membershipを削っていないことの確認になる。
- 試算バイト数は、元の状態にsamplerが返した行とstatusを差し替えてJSON化した大きさ。baselineの圧縮後と比較した比率で、元データ比ではない。通信路・submit・I/Oの固定費は含まない。
- owner参照は「1スナップショット×owner集合」の取得であり、魚雷行数に比例しない。owner削減率を魚雷行削減率と同一視しない。
- B43のapi field readsは`ownerTeamId`／`ownerType`／`type`／`position`が55,841（baseline 73,711）へ減る。`uiId`／`ownerId`／`shotId`は列挙のため不変（95,413）。

### capの選択統計（分類tick）

| 指標 | B43 | B44 |
| --- | ---: | ---: |
| 25超過した分類tick | 25／48 | 0／30 |
| のべnear超過本数 | 1,224 | 0 |
| のべeligible（非自艦near・再分類済） | 1,851 | 121 |
| のべ選択（25枠） | 637 | 121 |
| のべspill | 1,214 | 0 |
| 選抜最遠のL比 中央値 | 0.0845 | 0.1321 |
| 選抜最遠のL比 最大 | 0.1788 | 0.1973 |
| top25同owner最大占有 | 11 | 6 |
| 分類tickのhigh↔low反転（のべ） | 363 | 7 |
| 分類tick最大high | 185 | 21 |
| 例外high総数（25枠外） | 387 | 3 |
| 例外high最大（1tick） | 185 | 2 |

- 選抜最遠（25位）のL比の中央値はB43で0.0845、最大0.1788（≒L/5の42%〜89%）。25枠はおおむねL/5の内側半分に収まる。
- 分類tickのhigh↔low反転はB43で363回。spill行が距離順位の入れ替わりで選択／非選択を往復するためで、これはcap固有の挙動。
- top25同owner最大占有はB43で11、B44で6。単一ownerが25枠の半数近くを占めるtickはあるが、25枠全体を独占するtickは無い。
- 例外highの総数はB43で387。うち初回分類tickの全行new（185）が最大の山。総highは25で縛られない。

### 分類された距離帯（分類tickののべ）

| 指標 | B43 baseline | B43 candidate | B44 baseline | B44 candidate |
| --- | ---: | ---: | ---: | ---: |
| near | 1,861 | 1,861 | 122 | 122 |
| far | 1,559 | 1,559 | 256 | 256 |
| unknown distance | 369 | 369 | 0 | 0 |
| classified | 3,789 | 3,789 | 378 | 378 |
| new | 20 | 20 | 3 | 3 |
| group change | 284 | 440 | 45 | 45 |
| provisional high | 20 | 20 | 3 | 3 |
| pruned | 8 | 8 | 0 | 0 |

- near／far／unknown／new／provisional／prunedは不変。距離計算そのものは変えていない。
- B43のgroup changeが284→440へ増えるのは、同じnear内でspill行がhigh↔lowを往復するため。B44はnearが少なく超過しないので不変。

### near行の距離分布（L比、分類tick）

| 距離帯（L比） | B43 | B44 |
| --- | ---: | ---: |
| 0.00–0.04 | 196 | 5 |
| 0.04–0.08 | 460 | 22 |
| 0.08–0.12 | 480 | 47 |
| 0.12–0.16 | 351 | 27 |
| 0.16–0.20（≦L/5） | 374 | 21 |

baselineとcandidateで同一（分類幾何は共通）。全near行のうちLOW化された行はB43で**11,936**、B44で0。

### サンプル間隔とmotion

| 指標 | B43 baseline | B43 candidate | B44 baseline | B44 candidate |
| --- | ---: | ---: | ---: | ---: |
| `dt > 1.0`秒 | 0 | **0** | 0 | **0** |
| 速度unknown | 350 | **350** | 64 | **64** |
| unknown理由 | firstObservationのみ | firstObservationのみ | firstObservationのみ | firstObservationのみ |

- spill行は平均2Hz（0.5秒）を維持するため、`TorpedoMotion`の`0 < dt <= 1.0`契約を外れない。**far 1Hz候補で問題になった速度unknown増加（80〜95%）は本capでは発生しない。**
- 実記録ではmid帯（0.5秒）でも稀に1.0秒を超える件があったが、本capは全spillをlow 2Hzに置くため、B43／B44とも`dt > 1.0`は0件だった。

## B09の静的幾何（リプレイではない）

B09は既にサンプル済みのため、分類tickの現在位置だけを使った。非分類tickの欠測は復元していない。L/5境界は、自己位置と較正diagの地図短辺から計算した。**完全5秒scheduler replayではない。**

| 指標 | セッションA | セッションB |
| --- | ---: | ---: |
| 状態数 | 919 | 677 |
| 全detail行 | 16,904 | 13,844 |
| 分類tick | 37 | 28 |
| 同時刻の最大行数 | 87 | 87 |
| near（L/5以内） | **324** | **248** |
| far | 405 | 365 |
| unknown distance | 0 | 0 |
| eligible（非自艦near） | 324 | 248 |
| 25超過した分類tick | 5 | 4 |
| のべnear超過本数 | 28 | 34 |
| のべ選択（25枠） | 296 | 214 |
| のべspill | 28 | 34 |
| 選抜最遠のL比 中央値 | 0.1468 | 0.1471 |
| top25同owner最大占有 | 6 | 9 |

- near 324／248と最大行数87は、旧`docs/RESEARCH_RADIUS_L5_B09.ja.md`のL/5 near値と一致した。分類tickの幾何としては再現できている。
- B09はB43よりnear比重が小さく（分類tickで最大38本）、25超過tickは37中5、28中4にとどまる。**highcap見込みは限定的**。
- 全detail行に対する削減率へ外挿しない。分類tick以外の行は、その時点の帯が分からない。

## 合成216本／22 ownerのホスト計測

5反復×300tick、合計1,500tick。魚雷216本の固定配置。cap選別コスト（距離ソート）を含む。

| 配置 | 指標 | baseline | candidate | 差 |
| --- | --- | ---: | ---: | ---: |
| allNear（near216） | サンプル行 | 324,000 | 166,425 | **-48.63%** |
| | high／low | 324,000／0 | 61,375／105,050 | |
| | owner参照 | 27,000 | 22,050 | -18.3% |
| | 中央値（ms/tick） | 6.78 | 4.65 | -31.4% |
| halfNear（near108・far108） | サンプル行 | 234,900 | 166,425 | -29.15% |
| | high／low | 175,500／59,400 | 61,375／105,050 | |
| | owner参照 | 27,000 | 27,000 | 0 |
| | 中央値（ms/tick） | 5.65 | 4.61 | -18.4% |
| ownMixed（near189・far27・own54） | サンプル行 | 324,000 | 210,975 | -34.88% |
| | high／low | 324,000／0 | 135,625／75,350 | |
| | owner参照 | 33,000 | 32,175 | -2.5% |
| | 中央値（ms/tick） | 6.89 | 5.44 | -21.0% |

- ownMixedのcandidate high（135,625）がallNear candidate high（61,375）を大きく上回るのは、真の自艦54本が常時highで25枠外だから。own例外の挙動が反映されている。
- これは**ホストPython 3＋安価な合成getter**の数値で、ゲーム時間でもFPSでもない。実ゲームの改善率として引用しない。中央値の低下は主にサンプル行数とposition読取りの減少によるもので、**cap選別そのもののコストはこの差に埋もれている**。
- 速度unknownは全配置でbaseline＝candidate（1,080）。合成tickは正確に0.2秒のため、low 0.5秒でも`dt > 1.0`は出ない。

## 25枠の例外と情報損失

- **初回分類の全行new**：キャッシュが空の初回は全行が`new`扱いでhighになる（B43で185、B44で21）。5秒間は25を超える。初回だけでなく、新規出現のたびに同様の一時超過が起きる。**総highは25で縛られない。**
- **unknown距離／unknown・duplicate識別**：距離が読めない、identityが不正、重複の行は安全側high。重複は「両方の出現」がduplicateになるため、元の行も枠から外れる（これも例外側でhighのまま）。
- **context loss**：安全側highへ即時昇格し、low行の次のdueを待たない。
- **情報損失**：25位以下のnear行は5Hz→2Hzへ落ちる。位置の更新頻度は半減し、`TorpedoMotion`の速度は0.5秒差分のまま得られるが、鮮度は下がる。viewerの表示保持は`group === 'low'`で1.5 game秒なので、2Hzの0.5秒間隔は保持余裕の内側にある。
- **距離順≠脅威順位**：距離だけでは衝突コースや誘導先を表さない。本capは「近い順に25本」であって「危険順に25本」ではない。CPA・誘導先推定はscope外。

## 検証テスト

`tests/test_torpedo_high_budget_25_research.py`（16件）。

- 26本→最寄り25本をhigh、最遠1本をlowへspill（境界包含、選抜最遠の距離・L比）。
- 同距離tieを列挙順で解決（int/str混在IDでも比較例外を出さない）。
- ownは全距離highかつ25枠外（own near 1のとき総high 28＝25＋3own）。境界（ちょうどL/5はnear、+0.0001はfar）。
- 消失後は次分類tickでのみ枠が空く。new／unknown距離／unknown識別／duplicateの例外。
- context lossの安全側high、clear／clock rollbackの初期化、自艦移動は再分類時のみ反映。
- far非dueのgetter 0（position読取り0・owner参照0）、collection 1、own current cache予算維持。
- wireはhigh/lowのみでcap metadataが乗らないこと、JSON安全。
- 合成216本／22 ownerの3配置（own除外）。
- private再生（B43／B44）は`WOWS_HIGH_BUDGET_25_REPLAY=1`時のみ。
- MiMo統合指標（high↔low反転、top25同owner最大、例外high総数・最大、分類tick最大high）は一時記録でのreplayテストで検証。

## 判断

**今回は採用しない。** 理由は次のとおり。

- 効果が**記録依存**。B43は25超過が25tickあり削減が大きいが、**B44はcap効果ゼロ**。近距離の同時多発が起きるかは戦況次第で、常時の利得ではない。
- 上限が**瞬時には効かない**。初回分類・新規出現時に全行new→highとなり、5秒間は25を超える。厳密な同時サンプル上限としては機能しない。
- **距離順は脅威順位ではない**。上位25本の選別基準に距離以外（CPA等）を入れるかは別設計。
- 一方で、**速度・`dt`契約を壊さない点はfar 1Hz候補より安全**。spillは2Hzに留まり、motionの速度unknownは増えない。

再検討の条件は次のとおり。

- 近距離同時多発の頻度を、戦況別（B43／B44／B09に限らず）に測る。capが効く局面がどれくらい常態かを先に確認する。
- 初回・新規出現時の一時超過（総high）を許容できるか、product判断を先に決める。
- 選別基準を距離以外にするなら、CPA等の推定とそのコストを別途設計・検証する。
- ゲーム内で、魚雷表示の追従、UIの選択、owner参照、通信量を測る。ホスト計測の時間差は使わない。

代替として、現行2Hzを維持したままwire圧縮やowner参照の固定費を減らす方が、consumer契約を変えずに済む。今回の測定だけでは、25枠上限を導入する根拠は得られなかった。

## 制約

- B43／B44はATMなしの特定セッションで、全魚雷位置がある未サンプル記録。**全行`isOwn`／`owner.isPlayer`がNone**のため、own挙動はunit／合成でのみ検証した。B09はATMあり・L/3時代の既サンプル記録で、静的分類tickのみ。
- baselineの再現一致は確認したが、candidateのゲーム内周期・FPS・通信路の実費用は未計測。
- バイト数はJSON化した試算で、submitやI/Oを含まない。サンプル行削減とFPS削減を同比例換算しない。
- owner参照はスナップショット単位であり、行数削減と比例しない。
- 合成は正確な0.2秒tick・安価なgetterで、実記録のjitterや実ゲームのコストを再現しない。Python 3安価getterのタイミングを実ゲームへ換算しない。
- B09の分類tick幾何を全tickの削減率へ外挿しない。B09を完全5秒replayと呼ばない。
- cap metadataはadapter-localであり、wire契約ではない。capのwire表現は未決定。

## 再現コマンド

```powershell
cd WowsExtractor-torpedoes-client-test
python tools/compare_torpedo_high_budget_25.py `
  --recording recordings/without-atm-b43.jsonl `
  --recording recordings/without-atm-b44.jsonl `
  --b09 recordings/with-atm-b09.jsonl `
  --synthetic --repeats 5 --ticks 300 `
  --json-output "$env:TEMP\hb25.json"
```

```powershell
python -m pytest tests/test_torpedo_high_budget_25_research.py -q
$env:WOWS_HIGH_BUDGET_25_REPLAY='1'
python -m pytest tests/test_torpedo_high_budget_25_research.py -q
```

## 追加・変更したファイル

- `tools/torpedo_high_budget_25_candidate.py`：テスト専用の距離順25枠sampler。
- `tools/compare_torpedo_high_budget_25.py`：B43／B44再生、B09静的幾何、合成ベンチマーク、MiMo統合指標。
- `tests/test_torpedo_high_budget_25_research.py`：境界、tie、own、例外、context loss、clear／rollback、自艦移動、getter予算、wire、合成、private再生の検証。
- 本稿。

`res_mods/`以下のランタイムソース、installer、viewer、記録、`.gitignore`、`.ai`の追跡変更は行っていない。commit／pushもしていない。
