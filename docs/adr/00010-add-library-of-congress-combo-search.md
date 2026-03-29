# ADR 00010: Add Library of Congress combo search

- Status: accepted
- Date: 2026-03-28
- Supersedes: none
- Superseded by: none

## Context

`Wikidata -> Wikimedia Commons` と `Wikidata person -> The Met` の補助だけでは、組み合わせ充足率の改善幅が限定的だった。

目標は 13 era × 30 country × 2 gender の高粒度マトリクスで 5 件達成率を大きく引き上げることであり、人物名起点だけではなく、組み合わせそのものを直接検索できる追加ソースが必要になった。

Library of Congress の写真 API は次の条件を満たす。

- API キー不要で JSON 取得できる
- 画像 URL、日付、タイトル、権利情報を 1 レスポンスで取りやすい
- `country + portrait + gender term` のクエリで一定量の候補が見込める

## Decision

Library of Congress を、人物名補完ではなく `country × era × gender` の組み合わせ直検索ソースとして追加する。

実装方針は次の通りとする。

- Wikimedia 系の回収後、目標件数に届いていない組み合わせだけを LoC で補完する
- クエリは `country + portrait woman/man` を基本にする
- 年代は検索後に API レスポンスの日付を解析してフィルタする
- ライセンスは `rights_advisory` が public-domain 系である場合、または古い年代について age heuristic を使って許可する

## Consequences

人物名が分からない組み合わせでも、肖像そのものを直接見つけられるようになる。

一方で、LoC の日付や地域情報はタイトル検索ベースのノイズを含むため、後続で query tuning や追加フィルタを続ける必要がある。
