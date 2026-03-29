# ADR 00013: Add Wellcome direct search

- Status: accepted
- Date: 2026-03-29
- Supersedes: none
- Superseded by: none

## Context

`Art Institute of Chicago` と `Cleveland Museum of Art` の追加で収集率は改善したが、なお古代〜近代・女性・一部国籍で不足が大きい。

追加候補を調べると、Wellcome Collection の catalogue API は次の条件を満たしていた。

- API キー不要
- `query` ベースで人物画像系の検索ができる
- `thumbnail.license` で Public Domain Mark を判定できる
- IIIF 画像 URL を使って直接画像取得できる

## Decision

Wellcome Collection を `country × era × gender` の direct-search ソースとして追加する。

実装方針は次の通りとする。

- `country term + portrait/woman/man` で検索する
- `title` / `lettering` / `physicalDescription` から年と国名を近似抽出する
- `thumbnail.license` が public-domain 系である候補だけを通す
- 取得済みの検索結果はページ単位でキャッシュし、era をまたいで使い回す

## Consequences

公開医療写真・歴史写真のような Wellcome 固有の画像群を拾えるようになる。

一方で、年代や国名はメタデータ文字列からの抽出なので、AIC/CMA と同様に近似検索のノイズは残る。
