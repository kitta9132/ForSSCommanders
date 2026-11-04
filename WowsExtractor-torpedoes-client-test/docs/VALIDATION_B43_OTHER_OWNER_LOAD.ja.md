# B43：自艦未発射・両陣営の大量魚雷

2026-11-04。ユーザー報告：11対12、シャトルーノー、自艦は未発射、minFPS30以上。カクつきは未報告。指定の2対2とは条件が異なる。ユーザーは通常PvPでこれ以上の負荷はないと想定しているが、描画・艦種・発見状況・魚雷量等の一般的上限を実証したものとは扱わない。

試験後にクライアントを停止し、collector13ファイルをhash照合してロード対象外へ退避。ATMは導入されていない。負荷拡大・通常戦・同条件の即時再試験は依頼していない。

## 記録の境界

私有JSONLを逐次解析。0.3.30-atm-derived-state。metaは2件、最初roster24はactive側と異なるbattleIdで、次roster23が全1,194 active stateと一致。inactive2件。古いmetaを今回のrosterや別の完了試験と混同しない。active範囲ts1267.4698～1512.9583（約245.49秒）。shipsは最大23、player indexHits合計22,115、個別vehicleLookups0。

平均更新間隔0.20577秒、中央値0.20500秒、最小0.20000、最大0.43502秒。各種追加sampler・heavy diagnostics・profilerはOFF、core5Hz。

## 魚雷・所有者の取得

- 魚雷なし493 state、魚雷あり701 state。同時最大216本、ownerId同時最大22種類。
- uiId/shotId/ownerId複合候補350種類。relation別では味方213、敵137。累積行は95,413、味方65,650／敵29,763。relationは直接ownerTeamIdとself teamの比較に基づき、ownerId→playerIdの推測joinではない。
- 全行でtorpedoStatus available、world positionあり。mapPosition available95,349、unknown64。unknownを推定座標で補完しない。
- owner返却は全95,413行でobject、teamIdはownerTeamIdと整合する集計値、isBotは全true。isPlayer/uiId/subtypeは全None。isOwnをユーザー申告から自動falseへ変更していない。
- owner.isAliveはtrue93,147／false2,266。これは返却値であり、魚雷の消失理由・誰がいつ撃沈されたかの証明ではない。
- motion available95,063、unavailable350（初観測等）。候補IDを全条件で普遍的な物理魚雷IDと保証しない。

これにより自艦以外の敵味方魚雷について公開owner取得・team relation・生位置を観測できた。ownerIdのplayerId/vehicleIdとの一般namespace契約、画面にない魚雷の完全性、被発見状態は未確定。

## 負荷の分かる範囲

記録行サイズはactive平均約124,948 bytes、最大253,711 bytes。外部recorderが生成したJSONL行のbyte数であり、collectorのstate.json write bytesと同一とは限らない。表示された全項目・多数魚雷の反復encodeが負荷候補だが、実時間の根拠ではない。

profilerは全activeで出力なし。従ってcollectorのAPI取得・owner lookup・motion／map計算・同期writeの時間値は今回得られていない。state間隔が約5Hzを保つこともFPS影響がない証明ではない。min30台の原因や、過去の6本試験から216本の費用を直線外挿して推定しない。

まずこの記録とsourceを使い、owner APIは既にsame-snapshot共有済みであることを踏まえて、残る意味保存型の削減候補を調査する。フレーム超え位置cache、魚雷の切捨て、owner状態の無期限cacheはしない。開始直後FPS低下は追跡対象外のまま。

## 追加のread-only解析とoffline予算確認

ownerIdと同stateのships.vehicleIdの型厳密一致は93,297行で一意、2,116行で未一致、複数一致なし。22 owner候補はすべて一度は一致した。meta rosterのplayerIdとの一致は0。これは複数ownerでの候補整合性であり、namespace契約の確定joinには昇格しない。

JSONL payloadの平均寄与はtorpedoes約56.1%、ships約20.8%、avatarObservations約16.6%。owner値をstate内のtableへ移す試算では全active約8.69%のbyte削減候補があるが、行内ownerを省くschema変更・consumer対応が必要。FPS改善の根拠はなく、今回は互換性を壊す圧縮を採用しない。

`test_torpedo_high_load_budget.py`で216魚雷・22 ownerのfixtureを追加。coreは216行を切り捨てず順序維持、collection getter1回、各owner lookup1回、失敗ownerも同sampleでは1回、次sampleでは再取得し古いalive/Noneを持ち越さないことを検証する。これはAPI-call予算のテストであって、実機時間・FPS改善の証明ではない。
