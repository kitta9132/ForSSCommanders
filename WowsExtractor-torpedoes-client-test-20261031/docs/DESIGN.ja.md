# 設計と未確認事項

この文書は初期設計・調査の履歴を含みます。直接UI読取りや差分運動情報はその後実装済みです。
現行0.3.1の取得可否は [SPEC_COVERAGE_0.3.1.ja.md](SPEC_COVERAGE_0.3.1.ja.md) を優先してください。

## 目的と現在の実装

目的は潜水艦での状況把握を補助する外部2Dマップへ、魚雷情報を供給することです。本版はそのうち **WoWSクライアント内で公開APIを読み、ファイルへ出す部分**です。

```text
公開ModsAPI v1
  ├─ battle.getAllTorpedoes()
  ├─ battle.getTorpedoOwnerById()
  └─ 自艦の発射管・選択弾情報
        ↓ TorpedoTelemetry
既存Collectorのstateスナップショットへ追加
        ↓ JSON化・既存ファイルライター
state.json / meta.json
        ↓ 任意
履歴記録ツール → JSONL
```

型・数値の意味を決めつけず、生のtypeとIDと位置を残す設計です。魚雷のtypeは固定の名称としてキャッシュせず、各収集時点で読み直します。

## typeを最優先する理由

公式SDK 15.9.0の `TORPEDO_MARKER_TYPE` には次が定義されています。

| 定数 | 値 |
| --- | --- |
| NORMAL | `normal` |
| DEEP_WATER | `deepwater` |
| ACOUSTIC | `acoustic` |
| MAGNETIC | `magnetic` |
| NOT_DANGEROUS | `not_dangerous` |

`GUIDED_TYPES` はACOUSTIC / MAGNETICです。`Torpedo` UIコンポーネントには `type:String` と `evTypeChanged` イベントがあります。
出典：[battle.xml](https://github.com/wgmods/ModSDK/blob/main/15.9.0/gui/data/constants/battle.xml#L564)、[Components.xml](https://github.com/wgmods/ModSDK/blob/main/15.9.0/gui/data/Components.xml#L2277)。

ただし、この表はUIマーカーの定義です。**公開Pythonオブジェクト `Torpedo.type` の値と常に同一だという保証は、この資料からは得られません。** そのため本版では未知の文字列も丸めずに出し、魚雷種類や誘導状態の分類を自動追加していません。

## ATMについて調べたこと

ATMは [AndrewTaro/AdvancedTorpedoMarker](https://github.com/AndrewTaro/AdvancedTorpedoMarker) です。調査した配布物のコミットは `6a62b202458484225369725f92b180f23af470d0`。

公開UI定義と、配布済みPython 2.7バイトコードの静的確認から、次を確認しました。ゲーム内で実行した確認ではありません。

- ATMの `markerType` は誘導レベル1なら`acoustic`、2なら`magnetic`を返します。
- `not_dangerous`の場合やレベル0の場合は、受け取ったtypeを返す分岐があります。レベル0なら常に`normal`へリセットする処理ではありません。
- ATMは必要な場合にUIの魚雷コンポーネントのtypeを補正し、変更イベントを発生させています。
- 現在誘導中かは別計算し、`mods_DataComponent.data.isHoming`へ渡します。
- `mods_DataComponent.data.isSpotted`もUIが参照します。これはクライアント側の発見距離の推定を含みます。

したがって、`acoustic` / `magnetic`は誘導レベル表示の情報として有用ですが、それだけで現在も誘導が継続しているとは判定できません。`magnetic`はここではUI列挙名であり、別の物理的な磁気魚雷と解釈しません。

ATM本体や署名済みファイルは本パッケージへ取り込んでいません。ライセンスの確認なしにATMコードを複製して実装することもしていません。

## 未実装の候補経路

### 直接のコンポーネント読み取り

v1の `dataHub` から、制限されていないコンポーネントを読める可能性があります。しかし、魚雷の `torpedoComponent.type` と `mods_DataComponent.data` を対象buildでv1 Pythonから直接取得できるかは未確認です。
本版には、このコンポーネント直接取得処理はありません。

### UI → Flash → Python

```text
ATMがUIの魚雷エンティティへ値を設定
 → 自作Unbound処理で生値を取得
 → 自作Main.swfへ渡す
 → flash.addExternalCallback()でPythonが受信
 → state.jsonへ追加
```

Flash→Pythonの公開コールバックは公式資料にあります。UIから独自SWFへ渡す実装と、魚雷IDの対応付け、エンティティ生成・消滅時の管理が未検証です。**全経路が実装済み／動作確認済みという意味ではありません。**
出典：[flash API](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/flash.md)。

### v2側からの出力

v2の開発手続きと適切な権限が得られるなら、必要な状態を取得して出す実装も候補です。`API_VERSION`の文字列を書き換えるだけでは実現しません。現行WG版の申請・署名運用の詳細は本パッケージで確認していません。

## 境界条件

- UIエンティティID、魚雷固有ID、発射元ID、プレイヤーID、shotIdは別の識別子として扱います。見た目が似ていても自動的に同一視しません。
- 将来isHomingを追加する場合、取得不可はnull、取得したfalseは非誘導という区別が必要です。
- マーカーが画面外で生成されない場合、表示インスタンスだけの監視では不足する可能性があります。コレクション単位の観測を検討します。
- 状態更新時にコンポーネントやdataオブジェクトが置き換わる可能性があります。古い参照の保持を前提にしません。
- 座標の差分から速度・航向は推定可能ですが、単位換算・時間差・座標系の検証が必要です。本版では算出しません。
- 残り射程や寿命は、発射以前を観測できなければ位置だけで確定できません。本版では出力しません。

## 実機で最初に答える質問

1. 魚雷一覧とtypeが出るか。
2. ping前後で同じ魚雷のtypeは変化するか。
3. ATMの有無で公開APIのtypeの挙動が変わるか。
4. ATM表示のtypeとAPI出力が一致する観測例を得られるか。
5. 一致しない場合、UI経路を試作する必要があるか。

この順に確認すれば、最初から未検証の橋渡し実装を導入せずに、必要な経路を判断できます。
