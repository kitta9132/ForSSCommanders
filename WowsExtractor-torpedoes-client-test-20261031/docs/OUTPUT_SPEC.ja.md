# WowsExtractor 魚雷出力版（WoWSクライアント用mod）

[Tz-WIND/8111_for_wows](https://github.com/Tz-WIND/8111_for_wows) のクライアント側収集modに、公開ModsAPIの魚雷情報出力を追加したものです。
ベースのコミット: `28470b6ff0c05bac8aa41bd7d986daa6814242e2`。
既存の `state.json` に魚雷関係のフィールドを追加します。
ゲーム外の任意ツールとして [簡易2Dマップ](SIMPLE_MAP.ja.md) とlocalhost読取り専用HTTPサーバーを含みます。

## この文書の対象

本版が書くJSONの仕様です。導入は [INSTALL.ja.md](INSTALL.ja.md)、typeの解釈とATMとの関係は [DESIGN.ja.md](DESIGN.ja.md) を参照してください。
公開API魚雷情報に加え、0.2.2以降はUIのtype/isHomingを診断枠で読み取ります。
0.2.3はisSpottedも追加します。実機の取得状況は [ACQUISITION_STATUS.ja.md](ACQUISITION_STATUS.ja.md)、
診断枠の仕様は [UI_PROBE.ja.md](UI_PROBE.ja.md) を参照してください。

## 追加する出力

既存の `ships`、`self`、`damage` などは維持し、トップレベルに次の3項目を追加します。

### `torpedoes`: 可視魚雷の配列

`battle.getAllTorpedoes()` の各 `Torpedo` について、公式資料に記載された7属性をすべて出力します。

| フィールド | 内容 |
| --- | --- |
| `uiId` | 魚雷のUI識別子 |
| `ownerId` | 魚雷の発射元識別子。プレイヤーIDや艦船IDと同一とは扱いません |
| `ownerTeamId` | 発射元のチームID |
| `ownerType` | 発射元種別のAPI値 |
| `shotId` | 射撃ID。同じ斉射の複数魚雷で共有される可能性があるため、魚雷単体の識別には使用しません |
| `type` | 魚雷種別のAPI値をそのまま出力 |
| `position` | `[x, y, z]` のワールド座標。取得できないときは `null` |

追加の整理情報:

| フィールド | 内容 |
| --- | --- |
| `relation` | 自艦のチームとの比較。`1`=味方、`2`=敵、不明=`null` |
| `owner` | `battle.getTorpedoOwnerById(ownerId)` が返す公開情報。取得できないときは `null` |
| `isOwn` | `owner.isPlayer` が真偽値として得られた場合の自艦判定。それ以外は `null` |

`owner` には、公開 `Player` / `Ship` の属性である `teamId`, `isObserver`, `isAlive`, `isBot`, `uiId`, `isPlayer`, `subtype`, `name`, `playerName` を出力します。公式資料では発射元の返り値がPlayerとされる一方、Shipの取得元にも同APIが記載されています。そのため両者の公開属性を読み、存在しない属性は `null` にします。関数として提供される属性を推測して呼ぶことはしません。

位置はAPIの生座標です。`y` をメートル単位の深度と断定せず、距離のメートル換算は行いません。
0.3.0は推定の速度・航向を別枠motionに追加します。詳細は [MAP_MOTION.ja.md](MAP_MOTION.ja.md)。
APIから消えた魚雷は次の正常取得フレームで配列から消えます。

### `torpedoStatus`: 取得状態

```json
{
  "available": true,
  "status": "available",
  "source": "battle.getAllTorpedoes"
}
```

| `status` | 意味 |
| --- | --- |
| `available` | 一覧の取得成功。`torpedoes: []` なら、その取得時点でAPIが返した可視魚雷は0本 |
| `unsupported` | クライアントに `getAllTorpedoes` が存在しない／呼べない |
| `unknown` | 例外、未準備、`None`、列挙途中の失敗など。魚雷0本とは判定できない |

失敗時は `available: false` と空配列を出します。古い魚雷情報を現在情報として残しません。

### `torpedoArmament`: 自艦の魚雷兵装

| フィールド | 内容 |
| --- | --- |
| `available` | 発射管状態または選択弾IDを取得できたか |
| `modulesStatus` | 自艦 `getTorpedoesModulesState()` の取得状態 |
| `modules` | 各発射管の `type`, `currentHP`, `maxHP`, `state`, `critTimer`, `position` をすべて出力 |
| `selectedAmmoStatus` | `getSelectedAmmoId(constants.WeaponType.TORPEDO)` の取得状態 |
| `selectedAmmoId` | 選択中の魚雷弾ID。未取得／無効値 `-1` は `null` |
| `ammoParamsStatus` | 選択弾IDに対する `getAmmoParams()` の取得状態 |
| `ammoParams` | 返り値の公開データ属性をJSON化したもの。未取得なら `null` |

各 `*Status` は `available` / `unknown` / `unsupported` です。発射管の `critTimer` はモジュールの故障関連タイマーであり、装填時間とは扱いません。

`getAmmoParams()` の公式説明は砲弾を中心に記述されているため、魚雷IDでもパラメーターを返すことは保証されていません。クライアントが公開する場合のみ出力します。属性名はクライアント依存で、速度・射程など特定の値が得られることは保証しません。非公開名とメソッドは対象外です。JSON化時は循環参照、非有限数、深さ6以上の複合値を `null` にします。

戦闘終了時の最終フレームは `active: false`, `torpedoes: []`, `torpedoStatus.available: false`, `torpedoStatus.status: "unknown"`, `torpedoArmament.available: false` です。
更新停止の検出は読み手側でファイル更新日時と `ts` を確認してください。

## 出力例

以下の値は説明用の架空値です。`type` / `ownerType` の実際の文字列はAPIの返り値に従います。

```json
{
  "schema": 1,
  "active": true,
  "torpedoes": [
    {
      "uiId": 123,
      "ownerId": 456,
      "ownerTeamId": 0,
      "ownerType": "Ship",
      "shotId": 789,
      "type": "normal",
      "position": [12.0, -3.0, 25.0],
      "relation": 1,
      "owner": null,
      "isOwn": null
    }
  ],
  "torpedoStatus": {
    "available": true,
    "status": "available",
    "source": "battle.getAllTorpedoes"
  },
  "torpedoArmament": {
    "available": true,
    "modulesStatus": "available",
    "modules": [],
    "selectedAmmoStatus": "unknown",
    "selectedAmmoId": null,
    "ammoParamsStatus": "unknown",
    "ammoParams": null
  }
}
```

これは追加項目の抜粋です。実際のファイルには既存の艦船情報なども入ります。ファイル書き込み途中に読む可能性があるため、読み手はJSON解析失敗時に再取得してください。

## 公開APIの範囲と確認状況

通常魚雷・誘導魚雷とも、公開APIが可視魚雷として返した分を同じ方法で出力します。
誘導先、誘導停止までの距離、残存射程、確定寿命、ピンガー命中状態は未取得です。
ATM由来の誘導・被発見状態はuiStateに分離し、type文字列から補完しません。

参照した公式資料（リビジョン `01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2`）:

- [battle API](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/battle.md)
- [Torpedoの全公開属性](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/Torpedo.md)
- [Ship](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/Ship.md)、[Player](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/Player.md)、[_ModuleState](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/_ModuleState.md)

公開APIの代替オブジェクトを使ったオフラインテストに加え、build 13357625で実機試験を行っています。
取得できた値・未検証条件の区別は [SPEC_COVERAGE_0.3.1.ja.md](SPEC_COVERAGE_0.3.1.ja.md) を参照してください。
ゲーム側の追加実測結果は [TEST_REPORT_TEMPLATE.ja.md](TEST_REPORT_TEMPLATE.ja.md) に記録できます。
元プロジェクトのサーバーはこの追加項目をHTTPへ自動公開しないため、外部ツールはまずmodが書く `state.json` を直接読んでください。

ライセンスは元プロジェクトと同じMITです。[LICENSE](../LICENSE) を参照してください。

## state.jsonのトップレベル全項目

以下は今回の収集器が生成する項目です。元プロジェクトのHTTPサーバーが付ける信封ではありません。`serviceId`, `instanceId`, `seq`, `availability`, `capabilities`, `objects`, `bounds` は本modのstateへ追加していません。

| キー | 型 | 内容 |
| --- | --- | --- |
| `schema` | 整数 | ファイル形式。`1` |
| `apiVersion` | 文字列 | ファイル出力契約。`1.0`。ゲーム用 `API_VERSION='API_v1.0'` とは別 |
| `battleId` | 文字列またはnull | 戦闘の識別。実IDが後から得られると途中で昇格することがある |
| `active` | bool | 収集器が戦闘中と認識しているか。明示的退場でfalse |
| `ts` | 数値 | `utils.getTimeFromGameStart()`由来。Unix時刻ではない。取得不能時は0になり得る |
| `self` | オブジェクトまたはnull | 既存の自艦情報 |
| `ships` | 配列 | 既存の艦船情報。条件により最終目撃情報も含む |
| `torpedoes` | 配列 | 今回追加した魚雷の現在フレームの一覧 |
| `torpedoStatus` | オブジェクト | 今回の魚雷一覧取得の状態 |
| `torpedoArmament` | オブジェクト | 自艦の魚雷発射管と選択弾の情報 |
| `uiTorpedoProbe` | オブジェクト | UI魚雷の読み取り診断。終了フレームでは省略 |
| `selfSystems` | オブジェクト | 自艦の消耗品・索敵装置の公開状態。終了フレームでは省略 |
| `damage` | オブジェクト | 既存のダメージ集計 |
| `ballistics` | オブジェクト | 既存の砲弾／航空機弾種の情報。魚雷誘導情報ではない |
| `diag` | オブジェクト | 既存の艦船収集に関する診断値 |

上表は通常フレームです。**終了フレームは軽量形**で、`schema`, `apiVersion`, `battleId`, `active`, `ts`, `ships`, `self`, `torpedoes`, `torpedoStatus`, `torpedoArmament`, `damage`を含みます。`ballistics`と`diag`はありません。`torpedoStatus.source`も終了フレームではありません。読み手は項目欠落を許容します。

### self（元プロジェクト継承）

候補フィールドは `playerId`, `teamId`, `health`, `maxHealth`, `yaw`, `speed`, `isVisible`, `isShipVisible`, `position`, `isObserver`。
属性の取得可否でキーの有無・nullが変わります。自艦を取得できないときは観戦艦を補助的に読む処理もあります。すべての値が常に揃う保証はありません。

### ships（元プロジェクト継承）

各行の候補フィールド：

- 識別・状態：`uiId`, `vehicleId`, `playerId`, `teamId`, `relation`, `alive`, `visible`。
- 属性・現在位置：`name`, `shipType`, `position`, `nx`, `ny`, `yaw`, `health`, `maxHealth`。
- 最終目撃：`lastPosition`, `lastNx`, `lastNy`, `lastYaw`, `lastHealth`, `lastSeenTs`, `staleSeconds`。

`relation`はこの収集器では原則1=味方、2=敵、不明=-1です。魚雷の不明値nullとは形が異なります。
艦船の位置には地図コンポーネントからの補助変換を含む場合があります。最終目撃情報は現在の敵位置ではありません。魚雷にこの最終目撃保持は適用していません。

### damage（元プロジェクト継承）

```json
{
  "inflicted": {"attackerId": {"total": 1000, "byVictim": {"victimId": 1000}}},
  "received": {"victimId": {"total": 1000, "byAttacker": {"attackerId": 1000}}},
  "teamTotal": {"teamId": 1000}
}
```

上は形の説明用です。実際のキーはIDを文字列にしたものです。未集計では3表とも空です。既存の補助推定・重複抑制のロジックを継承しており、魚雷だけを分類した戦果表ではありません。

### ballistics（元プロジェクト継承）

未取得時は `{"available": false}`。
取得時の候補は `available`, `squadronMode`, `ammoType`, `ammoId`, `penetration`, `impactSpeed`, `impactAngle`。
AP/CSでは `startRicochet`, `alwaysRicochet`, `overmatch`、APでは `detonatorDelay`, `detonatorThreshold`も候補になります。砲弾用情報・計算値であり、魚雷の速度や誘導停止距離として流用しません。

### diag（元プロジェクト継承）

候補は `totalShips`, `allies`, `alliesVisible`, `enemies`, `enemiesVisible`, `ghosts`, `mapCalib`, `mapSamples`, `uiHealth`。
`mapCalib`は地図座標の補助変換方式、`mapSamples`はその校正用サンプル数です。魚雷のtype取得成功を示す診断値ではありません。

## meta.jsonの全トップレベル項目

| キー | 内容 |
| --- | --- |
| `schema` | 1 |
| `apiVersion` | ファイル出力契約1.0 |
| `battleId` | 戦闘識別。stateと照合する |
| `mod` | `name=WowsExtractor`、`version=0.3.1-map-motion` |
| `ts` | 収集時刻。stateと同じゲーム由来の時間 |
| `battleType` | 戦闘種別。取れない場合gameMode等を補助として使う |
| `gameMode` | ゲームモード、欠損時null |
| `selfPlayerId` | 自プレイヤーID、欠損時null |
| `map` | 取得できた地図の公開属性 |
| `roster` | 既存の名簿・消耗品情報 |

`map`は動的です。候補は `geometryName`, `geometry`, `mapName`, `spaceName`, `spaceId`, `mapPath`, `name`, `mapId`, `arenaName`, `width`, `height`, `size`, `worldSize`, `spaceBounds`, `bounds`, `minX`, `maxX`, `minY`, `maxY`, `minZ`, `maxZ`, および認識用に補った `id`。常に境界が得られるわけではありません。

`roster[]`の候補は `playerId`, `teamId`, `relation`, `name`, `shipType`, `shipName`, `shipTier`, `consumables`。
`consumables[]`は `title`, `abilityId`, および公開属性から作る動的な `params`。これは魚雷の装填状態表ではありません。

metaは戦闘表示時に書き、遅れて到着する地図情報等のため初期に再試行することがあります。終了時に空のmetaへ置き換えません。stateとmetaは別ファイルなので、一方だけ新戦闘の状態になる短い期間があります。

## 読み手の契約

1. UTF-8のJSONとして読む。解析失敗や一時的なファイル欠落では再試行する。
2. `active`、`battleId`、`ts`とファイル更新日時を確認する。`ts`だけをUnix時刻として扱わない。
3. `torpedoStatus.available`がtrueの場合だけ、その回の配列を正常な観測として扱う。
4. `type`の未知値、null、他の任意項目の欠落を許容する。未知typeをnormalへ置き換えない。
5. 更新停止を終了と同一視しない。必要に応じ最後の観測を「古い」と明示し、現在の誘導状態として使わない。
6. IDの別名前空間を混ぜず、戦闘をまたいで同じ魚雷と扱わない。battleId昇格時は同じ戦闘の可能性も考慮する。

各収集間隔は目標値です。ディスク遅延や非同期ライターの最新優先によって、すべてのtickがファイルへ出る保証はありません。

## 型・欠損の補足

- 魚雷7属性とownerの候補属性は原則キーを持ち、取れない属性はnullです。positionもnullになり得ます。
- ownerのisAliveがメソッドとして返る場合、勝手に呼び出さずnullとして出します。
- 発射管modulesの空配列は、取得成功なら0個として扱います。取得失敗の空配列とはStatusで区別します。
- `torpedoArmament.available=true`でも、すべての下位項目が取れたとは限りません。下位Statusを確認します。
- 状態生成の外側の保護で例外を捕捉した場合、torpedoArmamentが `{"available":false}`だけになることがあります。
- 引数不足等の呼び出し例外はunknown、取得口自体がない場合はunsupportedです。細かい失敗理由をこの版のJSONは出しません。
# 0.3.2の出力変更について

現行の観測値・可視状態・最終目撃フィールド撤去は [OBSERVATIONS.ja.md](OBSERVATIONS.ja.md) を優先してください。
