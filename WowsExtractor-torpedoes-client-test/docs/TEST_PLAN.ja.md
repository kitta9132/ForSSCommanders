# 実機テスト手順

現在の優先順位は [TASKS.md](../../TASKS.md) を参照。AIが目的・mod版／build・ATM有無・使用艦・準備・操作順序・記録方法・確認項目を提示し、ユーザーがMeatProxyとして実施します。取得確認と意味の検証を分けて報告します。

以下の段階A以降は、初期の読み込み・魚雷type比較用の基本手順です。typeの変化は既に試験範囲で確認済みで、毎回の最優先課題ではありません。現行版はATM等が供給するisHoming/isSpottedも出力し、取得不可はnullです。0.3.2の実機結果と残る可視状態の意味の検証は [OBSERVATIONS.ja.md](OBSERVATIONS.ja.md) を参照してください。

## 準備

- 最初は訓練戦で、可能なら協力者と行います。
- ゲームのバージョン・build番号、導入mod、艦名、選択した魚雷種類を記録します。
- [履歴記録ツール](RECORDER.ja.md)を戦闘前から開始し、終了フレームを保存するまで止めません。
- 一度に多くの魚雷を撃たず、最初は1本または少数で識別しやすくします。
- テストの操作時刻をメモします。画面録画を併用すると、同じ魚雷のマーカーと記録を比較しやすくなります。

テスト記録は [テンプレート](TEST_REPORT_TEMPLATE.ja.md)に記入できます。未実施は「未実施」、分からないことは「不明」と書き、推測で埋めません。

## 段階A：読み込みと書き込み

| 手順 | 確認するもの | 判定 |
| --- | --- | --- |
| ゲームを起動 | ログの `[WowsExtractor] loaded` | mod読み込みの確認 |
| 訓練戦に入場 | `meta.json`、`state.json` | 正しい導入先に生成される |
| 戦闘中数秒待つ | `state.json` の `ts` と更新日時 | 更新が進む |
| メタ情報を見る | `mod.version` | 試験対象版（現在のソースは `0.3.43-self-id-observation`）である |
| 魚雷未発射 | `torpedoStatus` | `available`と正常な空配列を区別できる |

`torpedoStatus.status=unsupported/unknown` の場合は、0本と判定せず [問題の切り分け](TROUBLESHOOTING.ja.md)へ進みます。

## 段階B：ATMなしでの基本魚雷

1. 可能なら通常魚雷を1本発射する。
2. `torpedoes[]` の各行で `uiId`、`ownerId`、`shotId`、`type`、`position` を保存する。
3. 同じ `uiId` の位置が時間とともに変わるか確認する。
4. 命中または消滅後、正常取得フレームから魚雷が消えるか確認する。
5. 複数本同時に発射し、`uiId`・`shotId`の組み合わせを観察する。

`shotId`だけで1本を識別しません。まず `(battleId, uiId)` を中心に履歴を見て、`ownerId` / `shotId` も照合用に残します。IDが再利用された形跡があれば寿命区間を分けます。

## 段階C：誘導魚雷とping

可能な範囲で、同じ魚雷について次の順に観察します。魚雷が先に消滅した場合は無理に同じ行にまとめず、発射し直して別の試行とします。

| 状況 | 保存する内容 |
| --- | --- |
| 誘導魚雷を発射、まだping命中なし | `type`の生値、時刻、魚雷ID |
| 対象に1回目のpingが命中 | 操作／命中時刻、前後の `type` |
| 同じ対象・部位へ2回目が命中 | 操作／命中時刻、前後の `type` |
| pingが時間切れ | 画面で確認した失効時刻、前後の `type` |
| 対象が応急工作班などで解除 | 解除を確認できたか、前後の `type` |
| 魚雷が対象へ近づく | 誘導継続／停止の表示や動きと `type` の関係 |

**期待する結果を先に決めつけません。** ATMは誘導レベル1→`acoustic`、2→`magnetic`にマーカーを補正する処理を持ちますが、ATMなしの公開API値が同じ動きをすることは未確認です。

`normal` が出たことだけで、魚雷が誘導機能を持たない／誘導が無効、と断定しません。`acoustic` / `magnetic` が残っても、実際に誘導が続いているとは断定しません。ATMのレベル0の処理は単純に常に `normal` へ戻すものではありません。

## 段階D：ATMありで同じテストを繰り返す

1. ゲームを終了し、`restore-atm.bat` で退避したATMを戻す。必要なら現行版ATMと作者指定の依存modを導入する。
2. ゲームを再起動し、新しいファイル名で履歴記録を開始する。
3. 段階B・Cを同じ艦と魚雷種類で繰り返す。
4. ATMの波線／M表示と、同じ魚雷のAPI側 `type` を時刻付きで比較する。
5. ATMのフォーカス表示が消える際にも `type` がどうなるか記録する。

ATMの表示設定がOffなら表示を使った比較はできません。設定画面で確認します。Alt時だけ表示する設定ではキー操作もメモします。

ATMがUIのtypeを書き換える影響をAPI側も受ける可能性があります。**ATMなし／ありの記録を混ぜずに保管します。**

## 段階E：発射元・可視性

余裕があれば味方・敵の可視魚雷、航空魚雷も観察します。

- `ownerTeamId`、`ownerType`、`owner` が何を返すか。
- `isOwn=null` のままか、真偽値を得られるか。
- 自艦チーム比較による `relation` と、画面の味方／敵表示に違いがないか。
- カメラを外してもAPIの一覧に残るか、画面マーカーの有無で取れる範囲が変わるか。

空母系のチーム識別などは実際の返り値を優先し、整理情報の判定が必ず正しいとは前提にしません。

## 段階G：自艦 ID candidate 観測（0.3.43）

この段階は `self.identityCandidates` の実機取得と、`torpedoes[].ownerId` とのcandidate照合用です。距離heuristicや`ownerId==vehicleId`の推測joinを行わず、観測値を記録します。

### 最小試験：Minotaur 1対1 自己発射

- **build／mod**: 現行 source `0.3.43-self-id-observation`（導入は親担当）。
- **艦**: Minotaur（自艦）、味方／敵は同型1隻ずつが望ましいが、負担最小なら訓練戦1対1。
- **ATM**: 現在のATM・他modを保持する。`restore-atm.bat` は復元用であり、退避には使わない。
- **設定**: 前回の collection／profiler／独立群設定を保持する。state_interval は 0.2 s（5 Hz）。この試験のために設定を変更しない。
- **記録**: 全fieldレコーダーを戦闘前に開始。ファイル名ではなく実際の導入状態を条件として記録する。

### 操作順

1. 訓練戦に入場し、自艦が動けるようになってから魚雷を**1斉射**発射する。
2. 発射後、**20 秒間待つ**（5 Hzで約100 sample、魚雷が充分に離れる）。
3. 戦闘を終了／退場する。
4. 記録を停止する。

### 確認項目

- `state.json` / JSONL の `self.identityCandidates` が毎 sample 存在すること。
- `battle.getSelfPlayerInfo().id`（playerId）、`battle.getSelfPlayerInfo().shipId`（shipId）、`battle.getSelfPlayerShip().uiId` の status が `available` で、生値が取得できていること。
- Ship 非公開属性 `_Ship__id` / `id` / `vehicleId` は `nonPublicShipAttribute` として取得できていれば記録し、取得不能でも欠測として残ること。
- `torpedoes[]` の自艦発射行の `ownerId` と、上記 candidate のいずれかが同一値であっても、`isOwn` は `owner.isPlayer` の厳密 bool のみで決まり、推測で上書きしないこと。
- 味方・敵の魚雷が混在する場合、`self.identityCandidates` の値と `torpedoes[].ownerId` が一致するのは自艦発射行だけ（1戦でown/ally比較できる条件なら確認）。
- `analyze_self_id_candidates.py <記録.jsonl>` を実行し、各 candidate の `matchConsistency` / `crossCandidateConsistency` を確認する。

### 解析

```powershell
python tools/analyze_self_id_candidates.py recordings/without-atm-self-id-xxx.jsonl
```

出力は匿名集計のみ。生のID値は含みません。`consistentMatch` が出た candidate は `torpedo.ownerId` と同一 namespace の可能性を示すcandidateに留まり、確定joinではありません。

## 段階F：終了・再入場

1. 戦闘中の魚雷を記録した後、戦闘を終了／退場する。
2. 履歴内に `active:false`、`torpedoes:[]` の最終フレームがあるか確認する。
3. 次の戦闘へ入り、`battleId` が区別できること、前の魚雷が残らないことを確認する。
4. 記録ツールをCtrl+Cで停止する。

ゲームを強制終了した場合やクラッシュした場合は、終了フレームがないことがあります。これは「魚雷が存在し続けた」ことを意味しません。読み手が更新停止を判定する必要があります。

## 結果から次の経路を決める

| 観測結果 | 次に検討すること |
| --- | --- |
| APIのtypeがATM表示と同じ変化を示す | 現行の直接出力を主経路にする候補。厳密な内部実装の同一性までは未証明 |
| ATMありの場合だけ変化する | ATM依存の動作として明記し、継続観測する |
| ATMの表示は変わるがAPIのtypeは変わらない | UIコンポーネント側の取得／橋渡しを試作する必要がある |
| 魚雷は取れるがtypeがnull | 対象buildで公開属性を取得できない可能性。ログと記録を残す |
| 魚雷自体が取れない | まず公開APIの利用可否・読み込み・可視性を切り分ける |

いずれも「1回合った」だけで全魚雷・全視点・全艦種に一般化しません。

## 報告に必要な最小セット

- ゲームバージョン／build、mod.version、ATMと依存modのバージョン。
- 問題が起きた手順と、期待した結果・実際の結果。
- 対象魚雷のIDと、操作前後のJSONL数秒分。
- `[WowsExtractor]` 周辺のログ、可能なら同じ時刻のマーカー表示。

通常のフル記録にはプレイヤー名・IDなどが含まれます。共有前に確認します。`--torpedoes-only`でも発射元情報等は残るため完全な匿名化にはなりません。
