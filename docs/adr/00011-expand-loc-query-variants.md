# ADR 00011: Expand LoC query variants

- Status: accepted
- Date: 2026-03-28
- Supersedes: none
- Superseded by: none

## Context

Library of Congress の組み合わせ直検索は、初期実装で一定の改善を出したが、`140 / 780` 到達時点でも多数の組み合わせが 0 件のままだった。

特に次の 2 点がボトルネックだった。

- クエリが `country name + portrait woman/man` に固定され、`Japan` より `Japanese` のような表現差を拾えない
- 1 クエリあたり先頭 1 ページしか見ておらず、年代フィルタ後に有効候補が落ち切る

## Decision

LoC の直検索では、国名そのものに加えて主要な形容詞・デモニムも検索語として使い、さらに各クエリで複数ページを走査する。

実装方針は次の通りとする。

- 30 か国について `Japan/Japanese` のような検索語バリエーションをコード上で管理する
- gender term は既存の `portrait woman/man`, `woman/man` を維持しつつ、国名バリエーションと組み合わせる
- 各クエリで複数ページを取得し、年代フィルタ後も不足する場合だけ次ページへ進む
- fixture は既存命名を壊さず、追加バリエーションやページ番号付きファイル名も読めるようにする

## Consequences

LoC 由来の候補発見数は増えやすくなり、特に 0 件組み合わせの削減が期待できる。

一方で API リクエスト数は増えるため、必要に応じてページ数上限やクエリ順序の調整を継続する。
