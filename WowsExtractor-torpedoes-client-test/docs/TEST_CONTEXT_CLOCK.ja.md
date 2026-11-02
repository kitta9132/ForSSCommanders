# context／clock候補の短い実機確認手順

過去の次回手順。B11（0.3.6）でcontroller選択と9:40画面報告の整合は当該試験条件で確認済み。B12後にslot routeだけでは発射後tube reloadを覆えていないcoverage不足が判明したため、次の実機試験は0.3.8の[gun reload最小試験](TEST_GUN_RELOAD_0.3.8.ja.md)へ差し替え、時計・選択試験を重複しない。旧ログへ新clock式を遡及適用しない。

1. 親セッションが実施を判断したときのみ、訓練戦でMinotaurを使用し、通常の1本発射・再装填完了を1回観測する。追加発射や選択専用再試験は不要。
2. 操作時点で画面の残り時間、選択・発射・再装填表示を時刻とともに記録する。
3. JSONLで`weaponHubProbe`装填候補と`gameClockProbe.observations`直接raw／推定値を同じ`sampleTs`で照合する。raw `battleTime`/`duration`/`currentTime`と`inferredBattleRemaining`は別物として扱う。残り時間式は別named collectionの単一rowを同一snapshotで採った推定であり、同一entityではない。duration分・battleTime秒というscope assumptionとsource/statusを確認する。
4. 0/複数row、partial/truncated、nullまたはfield不明はunknown。単一rowを一般的なentity joinの根拠にしない。collection source・unit/enum・意味はunverifiedで、出力を確定サーバー情報と扱わない。

既存B09/B10の不整合は新clock観測を得た次の1回でのみ検討し、過去ログには遡及推測しない。退出約15.4秒とAI目安約10秒の差は不具合として扱わない。`weaponSlot.selected=false`単独をcontroller選択の否定と解釈しない。
