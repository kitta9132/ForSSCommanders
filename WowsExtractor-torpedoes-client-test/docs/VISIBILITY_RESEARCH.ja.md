# 可視候補とゲーム由来の最終発見時刻：調査（2026-11-01）

> 注記：この文書は2026-11-01時点の調査記録です。当時の `record-13357625.bat` は、現行の `record.bat` に改名されています。

この文書は静的参照の確認と試験計画であり、候補フラグの実機意味確定や最終発見時刻の取得確認ではない。調査対象は指定されたローカル抽出GUI資料とクライアント `res/scripts.zip` の指定エントリに限定した。実装変更・ゲーム起動・pyc実行はしていない。全体のコード調査文書は [`P1_CODE_RESEARCH.ja.md`](P1_CODE_RESEARCH.ja.md) を参照。

0.3.4の最新実機JSONL突合結果（候補値・遷移と残る制約）は [`VALIDATION_0.3.4_VISIBILITY.ja.md`](VALIDATION_0.3.4_VISIBILITY.ja.md) を参照。意味の一般確定ではない。

## 標準UIの参照元

ローカルの既存抽出資料 `../mino-smoke/research/extracted/gui/unbound2/` と `../mino-smoke/research/extracted/gui/unbound/markup.xml` を限定検索した。
資料は別プロジェクトの既存抽出物で、現行buildから今回再抽出したものではない。
したがって現行buildの定義と同一とは未確認。

- `unbound2/pc/battle/minimap/markers/ship_marker.unbound:45-46` は
  `visibility.mapVisible` と `visibility.visible` を別々に読み、後者を
  `worldVisible` と命名する。
- 同78行ではミニマップ上の方向線を `mapVisible` で制御する。同146行では
  `mapVisible && !worldVisible` に `_invisible` を付加する。
- 同160行では生存艦で `!mapVisible && !worldVisible` のとき
  `_last_visible` アイコンを選ぶ。最終目撃マーカーにも座標が使われるため、
  地図座標の存在を発見中の根拠にしてはいけない。
- `unbound2/pc/battle/markers/ship_marker.unbound:30-31` も両者を別々に読み、
  `worldVisible` はアイコンのラベル表示（同169行）に使われる。
- `unbound2/pc/battle/minimap/markers/base_marker.unbound:188,265` は
  `mapVisible`を選択ロック表示の条件に使う。`markup.xml` では
  `visibility.mapVisible`／`visibility.visible`および艦の最終目撃時刻の該当参照を
  見つけなかった。`lastSeen`検索に出たaccount-level pointsは艦の可視履歴と無関係。

以上で確定できるのは**当該UI資料での表示用途**のみ。
サーバーの発見状態、味方視界、潜航、観戦時の意味や更新遅延は未確定。
0.3.3ソース `Main.py` は`dataHub.visibility`から`mapVisible`、`visible`、`isVisible`、
`isShipVisible`を候補別に診断し、互換のraw辞書には有限な数値／boolを収集する。
出力の互換フィールド`visible`は
`mapVisible`の投影であり、rawの`visible`とは別物（`_build_ships` L1477-L1492）。
`worldVisibleSource`はraw `visible`が収集できた場合だけ設定される。
候補別の`dataHubCandidates`／`shipApiCandidates`はsource/raw/type/status/reasonを出力し、
欠落・None・read exception・非bool・component/CC-key状態を区別する。診断追加版の
実機アクセス可否は未確認。`visibility.status`と互換フィールドは旧挙動を保つ。
`uiMeaning=minimapMarkerVisibility` はUI用途の説明であって実機検証済みフラグではない。

## 最終発見時刻の経路調査

- 公開Mods API資料の固定commit
  `01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2` の
  `docs/PythonAPI/Classes/Ship.md` を確認。公開属性・メソッド一覧に
  最終発見時刻はない。
- 指定された `gui/unbound2` を `lastVisible|lastVisibility|lastSpot|lastSeen|visibilityTime|timeSince|lastDetection|lastSpotted|spotTime|spottedAt` 等で検索した。艦の最終発見時刻参照は見つからず、マーカーは2つのboolで表示を切り替える。
- クライアントzipの指定14エントリ（公開ModsShellのShip/Player/battleGate/dataHub/events/utilsGate、visibility関連6、DataHubExtended、ReplayのVehicleVisibility）は存在を確認。ヘッダはPython 2系pyc形式（magic `03f30d0a`、一部ファイルでは以降のmarshal versionも異なる）。ファイルは実行・marshal/dis解析せず、ASCII文字列走査も試したが、有意な平文識別子を確認できなかった。環境に `uncompyle6`、`decompyle3`、`xdis` はなく、依存導入もしない方針のため、コード内容・API署名・時刻候補の有無は判定不能。これは候補不在の証拠ではない。
- これは非公開Python/dataHub属性やゲーム内部にも値が存在しない証明ではない。
  現時点の取得可否は **unknown（確認した公開経路には未掲載）**。
  根拠のない属性名の総当たりや独自lastSeenTsによる代用はしない。
- 生時刻の供給元・単位・時刻基準を確認できていないため、時刻フィールドは追加しない。
  外部アプリで記録した変化時刻はアプリ観測時刻であり、ゲーム由来時刻ではない。

## 残る実機照合（完了条件）

目的：現行buildの2フラグと標準UI表示を対象ID・時刻で照合する。
対象：build 13357625、ソース版0.3.3-visibility-diagnosticsの配布物。
ATMなしを先に実施（本試験はATM不要）。ゲーム終了後に再導入する。

1. 自艦Minotaur、訓練戦で識別しやすい敵艦1隻。対象名とplayerId/vehicleIdを記録する。
2. `record-13357625.bat` でJSONLを収集し、標準ミニマップと時計が見える画面を録画する。
3. 対象を直接視認→島や煙幕で失探→再視認。各状態を10秒以上維持。
   各操作時刻、通常／最終目撃アイコン、3Dモデルの有無を記録する。
4. 可能なら味方だけが対象を発見する区間を追加し、その開始／終了時刻も記録する。
   協力艦なしで再現できなければ、その条件は未実施と報告する。
5. 正常退出し、JSONL・対象名・動画と時計の対応を提出する。

対象IDごとにraw.mapVisible/raw.visibleとUIの遷移を照合する。
欠測はfalseにしない。潜航条件はUndineで別試験にする。
全条件を再現せずサーバー発見状態一般と同一視しない。
実機なしではこの意味照合を完了にできない。

## 0.3.3で追加した限定診断

最終発見時刻フィールドは追加しない（由来・型・時刻基準を示す根拠なし）。0.3.3では4つのdataHub.visibility候補とPython ship API `isVisible`／`isShipVisible`を別sourceで診断する。候補単位でstatus/raw/typeと必要時reasonを出し、bool false、欠落、None、読取例外、非bool、componentなし、CCキーなしを区別する。unknownをfalseへ潰さず、rawには有限なbounded scalarだけを許可する。実機の属性アクセス可否・実値はこれから確認する。時刻は収集フレームのゲーム開始基準`now`と記録時刻を混同せず、ゲーム由来候補時刻が確認できない限り観測時刻を最終発見時刻として出さない。通常出力の意味は引き続き`unverified`。

## MeatProxy向け1試験手順（診断版）

これは候補を同一対象・同一戦闘のUIと照合する1試験。訓練戦の敵協力艦を前提にするが、敵協力者や条件を用意できなければその区間は未実施とし、同等結果を約束しない。

1. **導入前提**：診断を含むmod版、build 13357625、ATMなし、Minotaurを自艦として通常のrecord手順で開始する。導入／差し替えはゲームを終了してから行う。訓練戦で敵協力者1隻を対象に選び、対象艦名、playerId/vehicleId（記録に出る範囲）、マップ名をメモする。標準ミニマップと画面時計が読める録画を準備する。敵協力者を確保できない場合、試験はUI比較の成立条件不足と報告する。
2. **操作タイムライン**：記録開始後、対象が自艦から直接見え、ミニマップに通常表示される状態を10秒以上維持（A）。島影または遮蔽物へ移動し3Dモデルが消えた後も、ミニマップ表示の継続／消失を各10秒以上記録（B）。次に標準UIで最終目撃アイコンへ移るかを確認し、再び対象を直接視認して通常表示に戻る状態を10秒以上記録（C）。A/B/C各遷移で画面時計の時刻、モデル有無、ミニマップアイコン種別をメモする。可能ならBの間に味方だけが発見する条件を作り別区間として記録するが、協力艦が無い／再現できない場合は省略を明記する。
3. **Undineの第2フェーズ**：同じ試験計画の別戦闘として、ゲームを正常終了してから艦をUndineに変更し、同じbuild/mod/ATM条件で記録を取り直す。対象を視認できる浮上状態でA→B→Cを実施し、環境と安全が許す場合に限り、同じ遮蔽物条件で潜航状態の区間を追加して別ラベルにする。Minotaur戦とUndine戦は戦闘・艦ごとにログを分け、潜航比較をMinotaurの結果と混ぜない。Undineでの再現や敵協力艦の確保ができない条件は未実施とする（条件を作れるとは約束しない）。
4. **採取**：完全なjsonl、modログ/meta、A/B/Cおよび任意の味方発見区間のタイムライン、録画、mod版/build/ATM/艦/マップ情報。正常終了後に記録を回収する。公開時はアカウント名等を必要最小限にマスクし、対象IDは同一試験内で照合できる一貫した仮名にする。
5. **判定**：対象IDごとに候補別raw値・型・status/reason、座標/listingの状態、標準UIアイコンとモデル有無をA/B/C時刻で突合する。診断版導入前ログから`visible`候補の未取得や遷移を遡及判定しない。値がUIと相関してもその試験条件内の観察にとどめ、サーバー発見一般・味方視界・潜航の意味確定には広げない。最終発見時刻は本試験で外部記録した時刻とゲーム由来値を明確に分ける。

### 協力者なしで行うMinotaurの代替手順

訓練戦に入れる場合、敵協力者がいなくても自艦の直接視認→遮蔽物による失探→再視認を対象bot 1隻で記録できる。訓練戦でbotを配置できない場合は通常のCo-op戦で同じ手順を行い、交戦状況による中断を明記する。

1. ATMなし、build 13357625、0.3.3診断版で起動し、Minotaurを選ぶ。訓練戦では自艦以外に敵bot 1隻を配置し、可能なら戦闘開始地点近くの島影を選ぶ。味方botの動きで条件が変わる場合はその時刻をメモする。
2. 記録と画面録画を同時に開始。敵botが3Dモデルとして見え、ミニマップに通常表示される状態を10秒維持（A）。島の反対側へ移動し、モデルが完全に隠れた状態を10秒維持（B）。同じ対象を再び直接視認し10秒維持（C）。各区間のゲーム時計、playerId、モデル有無、ミニマップの通常／最終目撃アイコンをメモする。
3. JSONLの対象playerIdを同じに保ち、dataHub/shipApi候補status・rawとmapPositionRaw/listingをA/B/Cで比較する。味方だけが発見する区間は作れないため未実施と明記し、この試験から味方視界時の`visible`意味は推定しない。
4. botが動かない、対象IDを対応付けられない、戦闘が中断された場合はそのまま制約として記録する。ログ・動画に他プレイヤー名等が入る場合は外部共有前にマスクする。試験を成立させるための第三者参加や個別協力依頼は不要。

今回変更したファイルはこの調査文書とリポジトリルートの`TASKS.md`のみ。ソース、ゲーム、外部抽出物は変更していない。
