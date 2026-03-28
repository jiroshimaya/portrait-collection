# ADR 00001: Use Wikimedia pipeline for portrait collection

- Status: accepted
- Date: 2026-03-28
- Supersedes: none
- Superseded by: none

## Context

issue #1 では、時代区分・国籍・性別ごとに商用利用可能な肖像画像を再収集できる仕組みが必要になった。

手作業で候補を集めると再現性が低く、ライセンス確認も散在しやすい。公開 API から機械的に候補抽出し、画像とメタデータを同時に保存できる方式が望ましい。

## Decision

画像候補の抽出には Wikidata SPARQL endpoint を使い、画像とライセンス情報の取得には Wikimedia Commons API を使う。

時代区分は `fictional_scientist_quota_master_10000.csv` の `era_name`, `birth_year_band`, `birth_year_start`, `birth_year_end` をそのまま採用し、13 区分の `data/reference/era_definitions.csv` に固定化する。

国籍軸は参考元 CSV の主要国籍に寄せて、現代国名に正規化した 30 か国 (`data/reference/nationality_targets.csv`) を採用する。Wikidata クエリでは再現性と古代人物への対応を優先して「出生地を現代国家に射影した国名」を使用する。取得困難な組み合わせは `collection_summary.csv` の shortage reason に明示する。

issue 本文で「科学者でなくてもよい」とされているため、候補抽出は職業で絞り込まず、画像・年代・出生地・性別の条件を満たす人物全般から行う。

性別軸は現時点では Wikidata 上で比較的安定に取得できる `male` / `female` の 2 値を対象にする。

## Consequences

再実行可能な CLI を実装でき、画像・メタデータ・不足理由をまとめて保存できる。

一方で、Wikidata に十分な候補がない組み合わせや、Commons 上で商用利用条件を満たさない画像は不足として残る。必要に応じて対象国や fallback ルールを後続 ADR で拡張する。
