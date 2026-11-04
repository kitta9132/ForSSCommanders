# ATM連携後の残項目と最小確認計画

2026-11-04。Luna xhighによるread-only棚卸しと親のB08再集計。新規probeは不要と判断した。0.3.30の既存core／独立depth samplerを使い、成功済みの同条件試験を繰り返さない。

## 既存記録で進んだこと

- ATMありB08でisHoming/isSpotted導出候補のtrue/falseを取得。未供給遅延は初斉射約22秒、次斉射約2～3秒。1Hzを高速化して解決すると仮定しない。
- 同記録のlocatorはsearch state6→0、対応するconsumableもcurrentState6→0。最初のts177.7369でendTime-ts330秒、遷移時ts507.9324ではendTime-ts0。親も匿名再集計で一致を確認。**この記録内の数値整合候補**であり、HUD・API timebaseの一般契約としてremainingSecondsを追加しない。
- GUIの汎用CONSUMABLE_STATESには6=PREPARATION／0=READYというlabelがあるが、search API stateとの配線契約は未確認。distShip200やworkTimeLeft0も型・値を保持し、単位や未作動を推定しない。
- 斉射2群は観測できるがshotIdは魚雷ごとに異なる。shotIdを斉射IDとしない。

## 未確認のまま残すこと

- ownerIdとvehicleId/playerIdの一般的な同一性、敵味方のowner対応は未確定。getTorpedoOwnerById自体の取得とnamespace確定を分け、isOwnを推測補完しない。
- B40魚雷depth0.14は浮上条件のraw候補。別深度での変化、単位・基準面は未確認。B27自艦depthのm表示を転用しない。
- 誘導先ID・停止理由・消失理由は直接fieldの根拠なし。最寄り艦、命中報告、一覧消失から作らない。
- Search state／workTimeLeft／distShipの意味、consumable endTimeのtimebaseは画面の操作・状態変化と照合が必要。radar/hydro unknownを未搭載と断定しない。

## 次の1戦で確認する候補

協力者の手配を必須とせず、1対1の自艦Undineと魚雷搭載敵BOTで、(1)HUDで確認した非浮上深度から発射、(2)locatorの準備完了と作動1回、(3)敵魚雷がAPIに現れた場合だけownerを追加観測する。自艦潜水自体はB27成功済みであり再試験目的ではなく、今回は魚雷depth候補との対応が新条件。

core5Hz＋depth1Hz、heavy/state/profiler OFF、ATM不要。画面の深度・準備残秒・作動残秒と操作時刻を記録する。味方ownerは単独の1対1では確認できないので未確認として残し、無理に追加3人戦を要求しない。敵が魚雷を発射しない／可視APIに出ない場合も未取得のまま。深度・locatorの確認を敵発射成功に依存させない。

潜水艦locatorの初期準備約330秒を待つ負担があるため、深度発射と同じ戦闘へまとめる。ping成功や浮上発射、ATM連携の再確認、開始FPS低下の追跡はしない。
