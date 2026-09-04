# 浜名湖1M 展開予想AI Ver.2

6艇同時・条件付きMonte Carloによる「展開再現」型シミュレータ。前付け調整を①進入から②ST、③伸び・軌道、④攻防、⑤旋回・1M出口・バック中間まで伝播させる。

## Web版
`web/` は静的サイト。GitHub Pages / Cloudflare Pages にそのまま配置できる。現在はブラウザ内の軽量デモエンジンを搭載。

## 本物のMCエンジン
`backend/` はPython版統合MC。FastAPIで `/health` と `/simulate` を提供。実レースデータ校正前なので、公開サイトでは「構造統合版」と明示する。

## 公開時の注意
- 実データ・実動画・選手個人情報を公開リポジトリへ直接入れない。
- APIを公開する場合は認証、レート制限、入力上限を設定する。
- 現在の数値は実戦確率を保証しない。
- 実レースを複数レース検証してから浜名湖基準値を校正する。

## ローカルAPI
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

## 静的公開
GitHub Pagesはリポジトリから静的HTML/CSS/JSを公開できる。Cloudflare Pagesも静的HTMLを直接デプロイできる。

## 育成基盤（Ver.2.1）
- SQLiteにレース、シミュレーション、観測、検証履歴を保存。
- `/observations` と `/validation` で実戦比較を蓄積。
- `/calibrate` は30レース以上の検証履歴から候補モデルを作るが、自動active化しない。
- これにより「公開→実戦データ蓄積→検証→候補モデル→人が確認して更新」のループを構築できる。


## 実戦モード（Ver.2.1）
- `/live/prepare?date=YYYYMMDD&race_no=1..12` で浜名湖の公式出走表・直前情報を1レース単位で取得。
- 展示ST/展示タイム等が6艇揃った場合だけ `/live/simulate` を実行。欠損は推測補完しない。
- 実戦後は `/live/settle` で結果を保存し、予測との答え合わせへ進める。
- 大量巡回・動画自動取得は行わない。動画教師データは既存のローカル解析ルートを使用。
- 現段階では実データを入れて育てるための運用版で、浜名湖実戦精度を保証する校正済みモデルではない。
