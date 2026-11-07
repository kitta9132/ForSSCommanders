# 0.3.40以降の直接レビューと0.3.46補正

親エージェントが累積差分を確認し、runtimeの取得・分類・期限・設定・較正、および導入の保全経路を直接読んだ。委任先報告やテスト成功だけをレビューの代わりにしない。

## 直接確認した主要範囲

- `Main.py`：config、tick、battle start/quit、self ID候補、self/ships/torpedoesの同一sample共有、Eのgate、較正context、TTaro pending適用。
- `torpedo_telemetry.py`：設定正規化、厳密ID、チーム分類、初回・通常・context欠測、位置read計画、owner共有、membershipとwire。
- `map_calibration.py`：update/observe互換、live modelと診断snapshot分離、座標変換。
- 自作TTaro adapter/binding/schema：購読、初期read、dedup、fallback、解除、optional不在。
- installer：schema allowlist、hash、設定・loader・ATMの保持、backup/rollback。wrapper/build resolverの指定・不一致停止。
- 関連テスト・資料・ID解析CLI。研究toolの歴史baselineはprivate replayで別途回帰確認する。

## 検出・修正

1. **識別欠測でLOWが残る**：確認済み味方から自艦ID欠測／型不一致へ変わると、cached LOWが維持され得た。現在のunknown classはそのtickでHIGHへ昇格し、現在位置を読む。旧距離研究samplerにはこの新方針を適用しない。
2. **チーム型不一致を敵扱い**：型が異なるチームIDをenemyにせずunknownとする。型変換によるjoinはしない。
3. **TTaro次戦でINIへ戻る**：INI再読込後、adapterのrevisionが同じだとUI値を再適用しなかった。戦闘開始時にfallbackを更新し、UI初期readが同値でも取得元を識別して再適用する。TTaro不在で過去のfallbackをMainへ戻さない。
4. **観戦位置を遠近判定へ流用**：E③の自艦距離原点には非観戦・自艦ship存在時の位置だけを渡す。観戦／自艦不在では安全側core取得を維持する。
5. **新規schemaのrollback漏れ**：既存schemaの復元だけでなく、失敗時に新しく作成した自作schemaもロード対象外へ保全退避する。他schemaには触れない。
6. **匿名解析CLIの識別子漏れ**：self-ID解析CLIからbattleIdとローカルpathを除外する。内部解析結果は互換性を維持する。

## 残る制約と実機確認

- TTaroはprivate hubへのbuild依存アクセスを含み、公式な第三者安定API保証とは扱わない。実機で表示・通知を確認する。
- 敵20本枠は距離既知の敵の予算。ID不明・チーム不明・距離不明の安全側HIGHを含む全体本数の上限ではない。
- 自艦沈没後の現在位置欠測を古い位置で補完しない。距離不明時のHIGH増加は未解決の方針課題。
- E③はmap位置・visibility・IDをcore維持、farのworld位置・yawだけ低頻度化。較正に届くworld-map pairも減るため、実機の較正安定性は要確認。
- コンシューマーは非dueの省略／notSampledを失探・0・取得失敗へ変換しない。履歴・TTLは外部マップ責務。
- 直接レビューとoffline回帰は、実機の周期・FPS改善・全build互換性の証明ではない。

実機準備は回帰成功後に行い、既存ATM・他mod・configを保持する。起動成功と記録増加を確認してから、試験を継続する。

## 検証結果

Python 3.11で私有replay用環境変数3種をON：769 passed、14 skipped。skipは実行中のWoWSを変更しないinstallerガードによるもの。港状態確認・停止後にinstaller全20テストが成功し、計783件の全対象を確認した。11 module Python 2構文・収集経路checkerも成功。lib2to3の非推奨警告1件は残る。
