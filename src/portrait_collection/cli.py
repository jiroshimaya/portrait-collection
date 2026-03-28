from __future__ import annotations

import argparse
from pathlib import Path

from .collector import collect_portraits


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portrait-collection",
        description="Wikidata/Wikimedia Commons から肖像画像とメタデータを収集します。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="肖像画像を収集する")
    collect_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/portrait_collection"),
        help="画像とメタデータの出力先ディレクトリ",
    )
    collect_parser.add_argument(
        "--per-combination-target",
        type=int,
        default=5,
        help="時代区分・国籍・性別の各組み合わせごとの目標件数",
    )
    collect_parser.add_argument(
        "--image-width",
        type=int,
        default=512,
        help="Commons から取得するサムネイル横幅",
    )
    collect_parser.add_argument(
        "--eras-file",
        type=Path,
        default=None,
        help="時代区分 CSV のパス",
    )
    collect_parser.add_argument(
        "--countries-file",
        type=Path,
        default=None,
        help="国籍ターゲット CSV のパス",
    )
    collect_parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=None,
        help="ネットワークの代わりに fixture を使うディレクトリ",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "collect":
        summary = collect_portraits(
            output_dir=args.output_dir,
            per_combination_target=args.per_combination_target,
            image_width=args.image_width,
            eras_file=args.eras_file,
            countries_file=args.countries_file,
            fixtures_dir=args.fixtures_dir,
        )
        print(
            "収集完了: "
            f"{summary.portraits_collected} 件保存 / "
            f"{summary.combinations_filled} / {summary.combinations_total} 組み合わせが目標達成"
        )
        print(f"出力先: {summary.output_dir}")
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
