# ADR 00009: Expand portrait sources beyond Wikimedia

- Status: accepted
- Date: 2026-03-28
- Supersedes: none
- Superseded by: none

## Context

現状の収集パイプラインは Wikidata / Wikimedia Commons を主軸にしており、再現性とライセンス確認のしやすさは高い。

一方で、issue #1 の目的は「時代区分・国籍・性別の組み合わせをできるだけ網羅すること」にあり、Wikimedia だけでは候補が薄い組み合わせが多く残る。

ユーザーからも「Wikipedia 以外からも情報を探せるようにしたい」「商用利用可能な画像が取れるなら出典は問わず、属性組み合わせの網羅性を重視したい」という要望が出た。

## Decision

今後の収集拡張では、Wikimedia 以外の公開ソースも対象に含める。

優先条件は次の通りとする。

- API キーなし、または導入負荷が低い公開 API であること
- 商用利用可能な画像を機械的に判定しやすいこと
- 肖像・人物系データを一定量持ち、組み合わせ充足率の改善が見込めること

最初の追加ソースとして `The Met Open Access` を採用する。

候補ソースとしては、少なくとも次も検討対象にする。

- The Met Open Access
- Library of Congress
- Wellcome Collection
- Rijksmuseum
- Europeana

実装時は source adapter 方式を採用し、ソースごとに次を分離する。

- 候補検索
- ライセンス正規化
- ダウンロード URL 解決
- 共通メタデータ形式への変換

## Consequences

Wikimedia だけでは埋まりにくい組み合わせに対して、追加ソースから補完できる余地が生まれる。

一方で、ソースごとにライセンス表記・年代表記・地域表記の揺れがあるため、正規化ロジックとテストが増える。

この ADR により、今後の「収集元を増やす」「優先順位を変える」「採用見送り理由を残す」といった判断は、都度 ADR として追跡する前提を明確にする。
