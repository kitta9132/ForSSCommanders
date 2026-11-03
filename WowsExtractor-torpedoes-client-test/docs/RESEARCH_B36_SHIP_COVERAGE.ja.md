# B36：roster24とships20の取得範囲差

2026-11-03。Luna xhighの読取り専用調査と親の独立集計。現行収集sourceは0.3.24。開始直後のFPS低下は対象外。私有JSONLを逐次解析し、ID・名前は転記しない。

## 確認できた事実

- meta rosterは24人、両team12人。active全401 stateでavatarSnapshotStatusはcomplete/count24。
- shipsに一度でも現れたplayerIdは20種類。roster外IDは0、未出現は4人分（両teamの内訳1人と3人、全てBattleship）。未出現者のalive/positionは未観測であり、死亡・撃沈・失探と推定しない。
- `diag.totalShips`と出力ships件数は全stateで一致。内訳は11→11が9 state、13→13が2、16→16が1、18→18が1、20→20が388。
- `_build_ships`はgetAllShips由来の入力をループし、alive/relation/visibilityで行を除外せずout.appendする。writerと通常recorderにも4行を選択除外する処理はない。
- totalShipsは同じ入力のlenであって、独立したAPI完全性検証ではない。とはいえ本sourceと全stateの件数一致から、collector内の意図的フィルターで4行を捨てたという根拠はない。

## 結論と限界

**avatar/rosterは24、getAllShips由来の一覧は最大20という取得経路の範囲差**まで絞れた。ゲームAPI上流で4人分の艦が列挙されない理由は未確定。現存entity、読み込み、API列挙対象、その他上流事情のいずれとも決めない。player共有は返された艦一覧に対する対応解決であり、欠けた艦行を削除する処理ではない。

B28ではroster24に対しships24のstateが存在した。B33/B35ではroster12に対し序盤ships6から12へ増えている。これらは一覧の観測範囲が時点・試験で違う根拠だが、B36で4隻が未出現の理由を証明しない。

avatar24件の中に未出現4人のmapPositionやhealthが存在し利用可能かは、現在のships出力だけでは確認できない。complete/count24はentity列挙の成功であり、全component・全fieldの存在を保証しない。roster情報からaliveや位置を推測してshipsに4行を追加してはならない。

## 次の最小作業候補

追加getterなしで、入力取得状態・列挙完了状態・入力/処理/出力件数、rosterとの対応件数を別metadataとして計測できる。既存avatar snapshotから、ships未出現playerのmap/health取得可否を匿名の件数で確認する案もある。これで観測できた別経路の値は出所を分離して扱い、API艦行の取得成功と偽装しない。

現在は調査のみ。追加実機・補完実装はまだ行っていない。必要な観測を削らないことを優先し、API契約の根拠がないまま全roster＝全ship entityというassertを追加しない。
