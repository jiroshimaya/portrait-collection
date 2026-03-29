# portrait-collection

issue #1 に対応するため、Wikidata / Wikimedia Commons を主軸にしつつ、The Met Open Access と Library of Congress も補助ソースとして使える肖像画像収集 CLI を追加しました。

保存時には画像本体に加えて、`era_name`、`birth_year_band`、`nationality`、`gender`、引用元 URL、ライセンス情報をメタデータとして出力します。

## セットアップ

```bash
sh scripts/setup.sh
```

## 収集コマンド

既定の時代区分は、参照元 CSV と同じ 13 区分の `data/reference/era_definitions.csv`、国籍ターゲットは参考元 CSV の主要国籍を現代国名へ正規化した 30 か国の `data/reference/nationality_targets.csv` を使います。

```bash
uv run portrait-collection collect \
  --output-dir artifacts/portrait_collection \
  --per-combination-target 5 \
  --image-width 512
```

`artifacts/portrait_collection/metadata/` には次のファイルが出力されます。

- `portraits.jsonl`: 画像ごとのメタデータ
- `collection_summary.csv`: 時代区分・国籍・性別ごとの件数と不足理由
- `errors.json`: 取得失敗の記録
- `run_manifest.json`: 実行条件

画像本体は `artifacts/portrait_collection/images/` 配下に保存されます。

開発時に対象を絞りたい場合は、`--eras-file` と `--countries-file` で小さい CSV を渡して部分実行できます。

## 収集方針

- 時代区分は issue で参照された `fictional_scientist_quota_master_10000.csv` の 13 区分をそのまま採用
- 国籍は現代国名に統一し、収集上は「出生地を現代国家に射影した国名」を用いる
- 性別は現状の Wikidata 収集安定性を優先して `male` / `female` を対象
- 商用利用不可 (`NonCommercial`) の画像は除外
- 画像ソースは `Wikimedia Commons` を優先し、足りない場合は `The Met Open Access`、`Art Institute of Chicago`、`Cleveland Museum of Art`、`Wellcome Collection`、`Library of Congress` も使う
- `Library of Congress` では国名バリエーション（例: `Japan` / `Japanese`）と複数ページ走査で候補探索を広げる
- `Art Institute of Chicago` と `Cleveland Museum of Art` では direct-search の結果を era をまたいで再利用し、API 呼び出し数を抑える
- 各組み合わせで不足した場合は `collection_summary.csv` に理由を残す

詳細な設計判断は `docs/adr/00001-use-wikimedia-pipeline-for-portrait-collection.md` を参照してください。

## ライセンス

このリポジトリは MIT ライセンスの下で公開されています。詳細は [LICENSE](LICENSE) を参照してください。
