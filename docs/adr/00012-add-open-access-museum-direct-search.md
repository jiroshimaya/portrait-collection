# ADR 00012: Add open-access museum direct search

- Status: accepted
- Date: 2026-03-29
- Supersedes: none
- Superseded by: none

## Context

`Wikidata -> Wikimedia Commons` は候補不足が支配的で、`Library of Congress` は検索直打ちで一定の改善を出せた一方、`429 Too Many Requests` の影響を受けやすかった。

8 割目標に近づくには、同じく商用利用可能で API が公開されている別系統の組み合わせ直検索ソースを増やし、LoC 依存を下げる必要がある。

調査の結果、次の 2 ソースは今回の制約に合っていた。

- Art Institute of Chicago API: API キー不要、公開ドメイン判定と IIIF 画像 URL が使える
- Cleveland Museum of Art Open Access: API キー不要、CC0、画像 URL と年代情報が 1 レスポンスに入る

## Decision

Art Institute of Chicago と Cleveland Museum of Art を、`country × era × gender` の組み合わせ直検索ソースとして追加する。

実装方針は次の通りとする。

- どちらも `country term + portrait/woman/man` 検索を基本にする
- 同じ `country × gender × query term` のレスポンスは era をまたいで再利用する
- AIC は `is_public_domain` と `image_id` を必須にし、IIIF URL から画像を取得する
- CMA は `share_license_status = CC0` を必須にし、`images.web` を優先して取得する
- どちらも年代は API の start/end 系フィールドから era に再配分する

## Consequences

LoC 以外の direct-search 系候補発見が増え、外部 API の一時的な制限に対する耐性が上がる。

一方で、作品ベース検索なので人物の国籍や性別はタイトル・文化圏・説明文由来の近似になる。結果の質は引き続き fixture と実収集の両方で監視が必要である。
