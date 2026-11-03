# 0.3.24：残るcore負荷削減候補

2026-11-03。Luna xhighの読み取り専用レビューを整理。開始直後のFPS低下はユーザー指示で追跡対象外。mod再導入・追加実機試験・runtime変更は行っていない。24人roster対最大20艦の取得差は別調査中。

## 結論

B36のavatar平均3.935ms／cycle7.153msという記録は残る対象を示すが、avatar全体を削減可能という意味ではない。個々のgetter時間は未測定で、時計はtime.clock / basis assumed。**小さな重複削減候補はあるが、FPSを体感できるほど改善する根拠はまだない。** 以前の毎艦player取得削減と同等の効果を予告しない。

## 観測を削らない小さな候補

1. `Main._remember_roster_vehicles`は同じPlayerInfoをdamage登録と`_plain_player_row`で再読する。通常の完全な行ではplayerId/shipId/teamIdの約3 fieldが重複。24行なら約72 read/stateが候補。ただしdamage側のID正規化とindex側の型厳密判定は異なり、共通plain rowを作る場合も別々の解釈規則を保つ必要がある。0、alias、mapping/属性、例外、duplicate、partialを検証する。getPlayersInfo getter自体は既に1回であり、削減したと数えない。
2. `_build_ships`はpass1のdamage用とpass2の出力用でship.teamIdを再読する。同sampleのローカル値を共有すれば約1 read/艦行を省ける。B36では7,919行に相当するが、これは時間ではなく読取り数。同sample内の微小な取得時点変更は明示する。
3. AvatarRowsのcomponent値は既に共有済み。残るCC.avatar/vehicle/healthキーの行ごとの取得は、同capture内でまとめられる。N行なら3N回から3回が候補だが、CCキー参照であってゲームentity getter削減ではなく優先度は低い。

## 大きな変更を優先しない理由

- 群別の2Hz化は対象回数を減らせる一方、観測間隔が200msから500msへ延び、sample時刻・未sample・consumerの扱いを変える。現在の承認済み5Hz収集を無断で下げない。
- 同期submit平均0.981msは区間全体の記録値で、回収できる時間の保証ではない。serializer/native化は互換性と利用可否、off-thread化はAPI thread safety・GIL競合を評価する必要がある。
- mapping/属性fallbackの一律削除はAPI wrapperや欠測例外時の観測を壊し得る。部分的な判定回数だけの削減で大きなFPS効果を主張しない。

## 優先順

まず取得範囲（24対20）の問題を確かめる。上記重複削減は出力同値・call budgetをオフラインで検証できる小規模候補として残す。多数魚雷時の取得・motion・同期write増分は別途未検証。今回の調査だけで追加の実機再現を依頼しない。
