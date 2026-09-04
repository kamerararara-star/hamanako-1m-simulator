# 公開手順（Ver.2）

## 1. GitHub Pages（画面）
1. このフォルダをGitHubリポジトリへ配置。
2. `.github-workflow.yml` を `.github/workflows/pages.yml` に移動。
3. GitHubのPages設定でGitHub Actionsを選択。
4. push後にサイトが公開される。

## 2. Render（本体API）
`render.yaml` を使って `backend/Dockerfile` をデプロイする。
公開後、API URLを `localStorage.setItem('ver2_api','https://YOUR-API')` として画面から指定できる。

## 3. データ育成
- `/observations` に実測・教師データを保存。
- `/validation` に予測と実測の比較結果を保存。
- `/calibrate` は30検証レース未満なら待機、30以上で候補モデルを生成。
- 1レースだけでactiveモデルを変更しない。
- 実動画はローカルで解析し、6艇の対応が確認された教師候補だけ投入する。

## 4. 本番前チェック
- CORSを公開ドメインに限定する。
- APIキー/認証、レート制限、ログ監視を追加する。
- 実浜名湖データで複数開催を検証する。
- 実動画の6艇トラッキングを複数レースで校正する。
