from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from .axes import (
    CountryTarget,
    EraDefinition,
    SUPPORTED_GENDERS,
    default_country_file,
    default_era_file,
    load_country_targets,
    load_era_definitions,
    normalize_gender,
    slugify,
)
from .commons import (
    CommonsImageMetadata,
    download_image,
    fetch_image_metadata,
    is_commercially_usable,
)
from .wikidata import WikidataCandidate, fetch_candidates


@dataclass(frozen=True)
class PortraitRecord:
    portrait_id: str
    entity_id: str
    person_name: str
    birth_year: int
    era_name: str
    birth_year_band: str
    nationality: str
    gender: str
    source_url: str
    media_page_url: str
    image_file_title: str
    license_short_name: str
    license_url: str
    usage_terms: str
    artist: str
    credit: str
    local_path: str


@dataclass
class CombinationStats:
    target_count: int
    candidate_count: int = 0
    collected_count: int = 0
    license_rejected_count: int = 0
    download_failure_count: int = 0


@dataclass(frozen=True)
class CollectionSummary:
    output_dir: Path
    portraits_collected: int
    combinations_filled: int
    combinations_total: int


def collect_portraits(
    *,
    output_dir: Path,
    per_combination_target: int = 5,
    image_width: int = 512,
    eras_file: Path | None = None,
    countries_file: Path | None = None,
    fixtures_dir: Path | None = None,
) -> CollectionSummary:
    eras = load_era_definitions(eras_file)
    countries = load_country_targets(countries_file)
    stats = _build_stats(
        countries=countries, eras=eras, target_count=per_combination_target
    )
    records: list[PortraitRecord] = []
    errors: list[dict[str, str]] = []
    metadata_cache: dict[str, CommonsImageMetadata] = {}
    candidate_limit = max(25, per_combination_target * 10)
    output_dir.mkdir(parents=True, exist_ok=True)

    for country in countries:
        for era in eras:
            for gender in SUPPORTED_GENDERS:
                combination_key = _combination_key(
                    country.country_name, era.era_name, gender
                )
                combination_stats = stats[combination_key]
                try:
                    candidates = fetch_candidates(
                        country,
                        era=era,
                        gender=gender,
                        limit=candidate_limit,
                        fixtures_dir=fixtures_dir,
                    )
                except RuntimeError as error:
                    errors.append(
                        {
                            "country": country.country_name,
                            "era_name": era.era_name,
                            "gender": gender,
                            "error": str(error),
                        }
                    )
                    continue

                for candidate in candidates:
                    normalized_gender = normalize_gender(candidate.gender)
                    if normalized_gender is None:
                        continue

                    combination_stats.candidate_count += 1

                    if combination_stats.collected_count >= per_combination_target:
                        continue

                    metadata = metadata_cache.get(candidate.image_file_title)
                    if metadata is None:
                        try:
                            metadata = fetch_image_metadata(
                                candidate.image_file_title,
                                image_width=image_width,
                                fixtures_dir=fixtures_dir,
                            )
                        except RuntimeError as error:
                            combination_stats.download_failure_count += 1
                            errors.append(
                                {
                                    "image_file_title": candidate.image_file_title,
                                    "source_url": candidate.wikidata_url,
                                    "error": str(error),
                                }
                            )
                            continue
                        metadata_cache[candidate.image_file_title] = metadata

                    if not is_commercially_usable(metadata):
                        combination_stats.license_rejected_count += 1
                        continue

                    local_path = _build_local_path(
                        output_dir=output_dir,
                        country=country,
                        era=era,
                        gender=gender,
                        candidate=candidate,
                    )

                    try:
                        download_image(
                            candidate.image_file_title,
                            download_url=metadata.download_url,
                            destination=local_path,
                            fixtures_dir=fixtures_dir,
                        )
                    except RuntimeError as error:
                        combination_stats.download_failure_count += 1
                        errors.append(
                            {
                                "image_file_title": candidate.image_file_title,
                                "source_url": candidate.wikidata_url,
                                "error": str(error),
                            }
                        )
                        continue

                    combination_stats.collected_count += 1
                    records.append(
                        PortraitRecord(
                            portrait_id=_portrait_id(
                                candidate.entity_id, candidate.image_file_title
                            ),
                            entity_id=candidate.entity_id,
                            person_name=candidate.person_name,
                            birth_year=candidate.birth_year,
                            era_name=era.era_name,
                            birth_year_band=era.birth_year_band,
                            nationality=country.country_name,
                            gender=gender,
                            source_url=candidate.wikidata_url,
                            media_page_url=metadata.media_page_url,
                            image_file_title=candidate.image_file_title,
                            license_short_name=metadata.license_short_name,
                            license_url=metadata.license_url,
                            usage_terms=metadata.usage_terms,
                            artist=metadata.artist,
                            credit=metadata.credit,
                            local_path=str(local_path.relative_to(output_dir)),
                        )
                    )

                _write_outputs(
                    output_dir=output_dir,
                    records=records,
                    stats=stats,
                    countries=countries,
                    eras=eras,
                    errors=errors,
                    per_combination_target=per_combination_target,
                    image_width=image_width,
                    eras_file=eras_file or default_era_file(),
                    countries_file=countries_file or default_country_file(),
                )

    _write_outputs(
        output_dir=output_dir,
        records=records,
        stats=stats,
        countries=countries,
        eras=eras,
        errors=errors,
        per_combination_target=per_combination_target,
        image_width=image_width,
        eras_file=eras_file or default_era_file(),
        countries_file=countries_file or default_country_file(),
    )

    combinations_filled = sum(
        1
        for combination_stats in stats.values()
        if combination_stats.collected_count >= per_combination_target
    )
    return CollectionSummary(
        output_dir=output_dir,
        portraits_collected=len(records),
        combinations_filled=combinations_filled,
        combinations_total=len(stats),
    )


def _build_stats(
    *,
    countries: list[CountryTarget],
    eras: list[EraDefinition],
    target_count: int,
) -> dict[str, CombinationStats]:
    return {
        _combination_key(country.country_name, era.era_name, gender): CombinationStats(
            target_count=target_count
        )
        for country in countries
        for era in eras
        for gender in SUPPORTED_GENDERS
    }


def _build_local_path(
    *,
    output_dir: Path,
    country: CountryTarget,
    era: EraDefinition,
    gender: str,
    candidate: WikidataCandidate,
) -> Path:
    file_name = candidate.image_file_title.split(":", 1)[-1]
    suffix = Path(file_name).suffix.lower() or ".jpg"
    stem = slugify(Path(file_name).stem)[:80]
    era_directory = f"{era.birth_year_start}_{era.birth_year_end}"
    return (
        output_dir
        / "images"
        / country.country_code
        / era_directory
        / gender
        / f"{candidate.entity_id}_{stem}{suffix}"
    )


def _write_outputs(
    *,
    output_dir: Path,
    records: list[PortraitRecord],
    stats: dict[str, CombinationStats],
    countries: list[CountryTarget],
    eras: list[EraDefinition],
    errors: list[dict[str, str]],
    per_combination_target: int,
    image_width: int,
    eras_file: Path,
    countries_file: Path,
) -> None:
    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    with (metadata_dir / "portraits.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    with (metadata_dir / "collection_summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "nationality",
                "era_name",
                "birth_year_band",
                "gender",
                "target_count",
                "collected_count",
                "candidate_count",
                "license_rejected_count",
                "download_failure_count",
                "shortage_reason",
            ]
        )
        for country in countries:
            for era in eras:
                for gender in SUPPORTED_GENDERS:
                    key = _combination_key(country.country_name, era.era_name, gender)
                    combination_stats = stats[key]
                    writer.writerow(
                        [
                            country.country_name,
                            era.era_name,
                            era.birth_year_band,
                            gender,
                            combination_stats.target_count,
                            combination_stats.collected_count,
                            combination_stats.candidate_count,
                            combination_stats.license_rejected_count,
                            combination_stats.download_failure_count,
                            _shortage_reason(combination_stats),
                        ]
                    )

    with (metadata_dir / "errors.json").open("w", encoding="utf-8") as handle:
        json.dump(errors, handle, ensure_ascii=False, indent=2)

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "output_dir": str(output_dir),
        "per_combination_target": per_combination_target,
        "image_width": image_width,
        "eras_file": str(eras_file),
        "countries_file": str(countries_file),
        "countries": [country.country_name for country in countries],
        "genders": list(SUPPORTED_GENDERS),
        "portrait_count": len(records),
    }
    with (metadata_dir / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)


def _shortage_reason(stats: CombinationStats) -> str:
    if stats.collected_count >= stats.target_count:
        return ""
    if stats.candidate_count == 0:
        return "Wikidata 上で候補が見つからなかった"
    if stats.license_rejected_count >= stats.candidate_count:
        return "商用利用可能なライセンス条件を満たす画像が見つからなかった"
    if stats.download_failure_count > 0:
        return "候補はあったがダウンロード失敗が発生した"
    return "候補はあったが目標件数まで到達しなかった"


def _portrait_id(entity_id: str, file_title: str) -> str:
    return f"{entity_id}-{quote(file_title.split(':', 1)[-1], safe='').lower()}"


def _combination_key(country_name: str, era_name: str, gender: str) -> str:
    return f"{country_name}|{era_name}|{gender}"
