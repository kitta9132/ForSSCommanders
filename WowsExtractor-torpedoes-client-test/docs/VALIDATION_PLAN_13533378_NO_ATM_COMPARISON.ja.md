# build13533378：ATMなし比較・L/5調査との分離

更新：ユーザー指定により**この時点で比較テストは行わない**。B47は待機のみで、結果として扱わない。記録プロセスは残存していないことを確認、試験用collector11ファイルをhash照合退避済み。ATMの今回退避した3ファイルを既存restoreスクリプトで戻し、導入前baselineのATM／engine_config hashとmodフォルダー集合の一致、collector不在を確認した。追加試験・ゲーム起動はしない。代わりに[B09詳細プロファイラ](PERFORMANCE_WITH_ATM_B09_0.3.38.ja.md)を集計した。以下は取り消した準備時の記録。

2026-11-05。ユーザー指定でATMなしの12対12比較を準備する。同時に調べる半径変更案は**L/3→L/5**であり、近5Hz／遠2Hz・5秒再分類は維持する案。遠1Hz化ではない。半径変更は今回の実機へ混ぜず、現行L/3のまま記録する。

## 構成と比較の限界

- collector0.3.38、build13533378、heavy OFF、profiler・独立4群ON、core0.2秒。HP平均2Hz、比較／damage約1Hzは既存どおり。
- ATM専用3ロード対象だけを既存installerで退避する。共用TTaroModUtils／ModForge、既存loader、その他modやゲーム設定は変更しない。
- 今回はB09後に他mod一式が導入されている。B09の「collector＋ATM＋今回の依存のみ」と同条件ではないため、今回とB09のFPS差をATM単独の因果効果と断定しない。導入前のmod一覧とATM／engine_config hashをprivate保全する。
- ATM state samplerはOFF・provider=unknownとし、存在しない供給元を有効宣言しない。従ってcollector内のATM専用probe費用もB09と異なることを明示する。
- ユーザーは前回と同じbot魚雷戦の観察・ソナーでの魚雷発見を行えばよい。TTX・自艦ping成功の再試験は要求しない。実現した人数・艦構成を記録で確認する。
- 最低FPS・カクつき有無・およその退出時刻を報告してもらう。悪化時は即退出可。録画は任意。開始直後FPS低下の調査は再開しない。

## L/5試算

B09は既に5Hz／2Hzで間引かれた記録のため、非due位置を過去sampleや外挿で補って完全な反実仮想リプレイと称さない。取得済み位置で確定できる幾何差分・省略可能な範囲と、欠測で不明な部分を分ける。半径を3/5倍にすると円面積は9/25だが、魚雷の空間分布が均等とは限らず実測割合と混同しない。FPS改善率は観測なしに計算しない。

## 準備・撤収

起動中のWorldOfWarships64.exeをinstallerが検出して初回dry-runを拒否したため、対象buildの当該プロセスを停止して再度preflight成功。installer完了後にcollector10 source hash一致、ATM3ロード対象不在、その他modフォルダー集合とengine_config hashの維持を確認。今回のATM退避先を導入前baselineとhash照合して特定しprivate保全した。試験設定を書き込み、全field・待機期限なしの`without-atm-b47.jsonl`へ記録プロセス起動と出力先を確認済み。実機結果はまだ未取得。

終了後は両ゲーム実行名の停止確認、記録回収・collector照合退避を行う。他mod・生成UIを一括退避しない。今回退避したATMは、導入前baselineとhash照合して元のmodpack構成へ戻す。旧B09退避物や別buildを無条件復元しない。
