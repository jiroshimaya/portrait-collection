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
    assign_era,
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
from .artic import search_portraits_for_combo as search_artic_portraits_for_combo
from .cma import search_portraits_for_combo as search_cma_portraits_for_combo
from .loc import search_portraits_for_combo
from .met import search_portraits_for_person
from .wellcome import search_portraits_for_combo as search_wellcome_portraits_for_combo
from .wikidata import WikidataCandidate, fetch_candidates


@dataclass(frozen=True)
class PortraitRecord:
    portrait_id: str
    source_name: str
    entity_id: str
    person_name: str
    birth_year: int
    year_basis: str
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
    met_cache: dict[str, list[CommonsImageMetadata]] = {}
    candidate_limit = max(100, per_combination_target * len(eras) * 2)
    output_dir.mkdir(parents=True, exist_ok=True)
    collected_portrait_ids: set[str] = set()

    for country in countries:
        for gender in SUPPORTED_GENDERS:
            candidates_by_key: dict[tuple[str, str], WikidataCandidate] = {}
            for sort_order in ("asc", "desc"):
                try:
                    candidates = fetch_candidates(
                        country,
                        gender=gender,
                        limit=candidate_limit,
                        sort_order=sort_order,
                        fixtures_dir=fixtures_dir,
                    )
                except RuntimeError as error:
                    errors.append(
                        {
                            "country": country.country_name,
                            "gender": gender,
                            "sort_order": sort_order,
                            "error": str(error),
                        }
                    )
                    continue

                for candidate in candidates:
                    candidate_key = (candidate.entity_id, candidate.image_file_title)
                    candidates_by_key[candidate_key] = candidate

            for candidate in sorted(
                candidates_by_key.values(),
                key=lambda current: (current.birth_year, current.person_name),
            ):
                normalized_gender = normalize_gender(candidate.gender)
                if normalized_gender is None:
                    continue

                era = assign_era(candidate.birth_year, eras)
                if era is None:
                    continue

                combination_key = _combination_key(
                    country.country_name,
                    era.era_name,
                    normalized_gender,
                )
                combination_stats = stats[combination_key]
                combination_stats.candidate_count += 1

                if combination_stats.collected_count >= per_combination_target:
                    continue

                commons_metadata = metadata_cache.get(candidate.image_file_title)
                if commons_metadata is None:
                    try:
                        commons_metadata = fetch_image_metadata(
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
                    else:
                        metadata_cache[candidate.image_file_title] = commons_metadata

                collected_from_commons = False
                if commons_metadata is not None:
                    collected_from_commons = _maybe_collect_asset(
                        output_dir=output_dir,
                        country=country,
                        era=era,
                        gender=normalized_gender,
                        candidate=candidate,
                        source_name="wikimedia-commons",
                        source_url=candidate.wikidata_url,
                        metadata=commons_metadata,
                        stats=combination_stats,
                        records=records,
                        errors=errors,
                        collected_portrait_ids=collected_portrait_ids,
                        fixtures_dir=fixtures_dir,
                    )

                if combination_stats.collected_count >= per_combination_target:
                    continue
                if collected_from_commons:
                    continue

                met_results = met_cache.get(candidate.entity_id)
                if met_results is None:
                    try:
                        met_results = search_portraits_for_person(
                            candidate.person_name,
                            limit=max(2, per_combination_target),
                            fixtures_dir=fixtures_dir,
                        )
                    except RuntimeError as error:
                        errors.append(
                            {
                                "person_name": candidate.person_name,
                                "source_name": "the-met",
                                "error": str(error),
                            }
                        )
                        met_results = []
                    met_cache[candidate.entity_id] = met_results

                for met_metadata in met_results:
                    if combination_stats.collected_count >= per_combination_target:
                        break
                    _maybe_collect_asset(
                        output_dir=output_dir,
                        country=country,
                        era=era,
                        gender=normalized_gender,
                        candidate=candidate,
                        source_name="the-met",
                        source_url=candidate.wikidata_url,
                        metadata=met_metadata,
                        stats=combination_stats,
                        records=records,
                        errors=errors,
                        collected_portrait_ids=collected_portrait_ids,
                        fixtures_dir=fixtures_dir,
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

        for era in eras:
            for gender in SUPPORTED_GENDERS:
                combination_key = _combination_key(
                    country.country_name, era.era_name, gender
                )
                combination_stats = stats[combination_key]
                remaining = per_combination_target - combination_stats.collected_count
                if remaining <= 0:
                    continue

                artic_outcome = search_artic_portraits_for_combo(
                    country,
                    era,
                    gender,
                    limit=max(remaining * 3, per_combination_target),
                    fixtures_dir=fixtures_dir,
                )
                for error in artic_outcome.errors:
                    errors.append(
                        {
                            "country": country.country_name,
                            "era_name": era.era_name,
                            "gender": gender,
                            "source_name": "art-institute-of-chicago",
                            "error": error,
                        }
                    )

                for asset in artic_outcome.assets:
                    combination_stats.candidate_count += 1
                    if combination_stats.collected_count >= per_combination_target:
                        break
                    _maybe_collect_direct_asset(
                        output_dir=output_dir,
                        country=country,
                        era=era,
                        gender=gender,
                        asset_id=asset.asset_id,
                        person_name=asset.title,
                        reference_year=asset.year,
                        year_basis="object_date",
                        source_name="art-institute-of-chicago",
                        source_url=asset.source_url,
                        metadata=asset.metadata,
                        stats=combination_stats,
                        records=records,
                        errors=errors,
                        collected_portrait_ids=collected_portrait_ids,
                        fixtures_dir=fixtures_dir,
                    )

                remaining = per_combination_target - combination_stats.collected_count
                if remaining <= 0:
                    continue

                cma_outcome = search_cma_portraits_for_combo(
                    country,
                    era,
                    gender,
                    limit=max(remaining * 3, per_combination_target),
                    fixtures_dir=fixtures_dir,
                )
                for error in cma_outcome.errors:
                    errors.append(
                        {
                            "country": country.country_name,
                            "era_name": era.era_name,
                            "gender": gender,
                            "source_name": "cleveland-museum-of-art",
                            "error": error,
                        }
                    )

                for asset in cma_outcome.assets:
                    combination_stats.candidate_count += 1
                    if combination_stats.collected_count >= per_combination_target:
                        break
                    _maybe_collect_direct_asset(
                        output_dir=output_dir,
                        country=country,
                        era=era,
                        gender=gender,
                        asset_id=asset.asset_id,
                        person_name=asset.title,
                        reference_year=asset.year,
                        year_basis="object_date",
                        source_name="cleveland-museum-of-art",
                        source_url=asset.source_url,
                        metadata=asset.metadata,
                        stats=combination_stats,
                        records=records,
                        errors=errors,
                        collected_portrait_ids=collected_portrait_ids,
                        fixtures_dir=fixtures_dir,
                    )

                remaining = per_combination_target - combination_stats.collected_count
                if remaining <= 0:
                    continue

                wellcome_outcome = search_wellcome_portraits_for_combo(
                    country,
                    era,
                    gender,
                    limit=max(remaining * 3, per_combination_target),
                    fixtures_dir=fixtures_dir,
                )
                for error in wellcome_outcome.errors:
                    errors.append(
                        {
                            "country": country.country_name,
                            "era_name": era.era_name,
                            "gender": gender,
                            "source_name": "wellcome-collection",
                            "error": error,
                        }
                    )

                for asset in wellcome_outcome.assets:
                    combination_stats.candidate_count += 1
                    if combination_stats.collected_count >= per_combination_target:
                        break
                    _maybe_collect_direct_asset(
                        output_dir=output_dir,
                        country=country,
                        era=era,
                        gender=gender,
                        asset_id=asset.asset_id,
                        person_name=asset.title,
                        reference_year=asset.year,
                        year_basis="object_date",
                        source_name="wellcome-collection",
                        source_url=asset.source_url,
                        metadata=asset.metadata,
                        stats=combination_stats,
                        records=records,
                        errors=errors,
                        collected_portrait_ids=collected_portrait_ids,
                        fixtures_dir=fixtures_dir,
                    )

                remaining = per_combination_target - combination_stats.collected_count
                if remaining <= 0:
                    continue

                loc_outcome = search_portraits_for_combo(
                    country,
                    era,
                    gender,
                    limit=max(remaining * 3, per_combination_target),
                    fixtures_dir=fixtures_dir,
                )
                for error in loc_outcome.errors:
                    errors.append(
                        {
                            "country": country.country_name,
                            "era_name": era.era_name,
                            "gender": gender,
                            "source_name": "library-of-congress",
                            "error": error,
                        }
                    )

                for asset in loc_outcome.assets:
                    combination_stats.candidate_count += 1
                    if combination_stats.collected_count >= per_combination_target:
                        break
                    _maybe_collect_direct_asset(
                        output_dir=output_dir,
                        country=country,
                        era=era,
                        gender=gender,
                        asset_id=asset.asset_id,
                        person_name=asset.title,
                        reference_year=asset.year,
                        year_basis="object_date",
                        source_name="library-of-congress",
                        source_url=asset.source_url,
                        metadata=asset.metadata,
                        stats=combination_stats,
                        records=records,
                        errors=errors,
                        collected_portrait_ids=collected_portrait_ids,
                        fixtures_dir=fixtures_dir,
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
    source_name: str,
    asset_file_title: str,
) -> Path:
    file_name = asset_file_title.split(":", 1)[-1]
    suffix = Path(file_name).suffix.lower() or ".jpg"
    stem = slugify(Path(file_name).stem)[:80]
    era_directory = f"{era.birth_year_start}_{era.birth_year_end}"
    source_slug = slugify(source_name)
    return (
        output_dir
        / "images"
        / country.country_code
        / era_directory
        / gender
        / f"{candidate.entity_id}_{source_slug}_{stem}{suffix}"
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


def _maybe_collect_asset(
    *,
    output_dir: Path,
    country: CountryTarget,
    era: EraDefinition,
    gender: str,
    candidate: WikidataCandidate,
    source_name: str,
    source_url: str,
    metadata: CommonsImageMetadata,
    stats: CombinationStats,
    records: list[PortraitRecord],
    errors: list[dict[str, str]],
    collected_portrait_ids: set[str],
    fixtures_dir: Path | None,
) -> bool:
    portrait_id = _portrait_id(
        candidate.entity_id, f"{source_name}:{metadata.file_title}"
    )
    if portrait_id in collected_portrait_ids:
        return False

    if not is_commercially_usable(metadata):
        stats.license_rejected_count += 1
        return False

    local_path = _build_local_path(
        output_dir=output_dir,
        country=country,
        era=era,
        gender=gender,
        candidate=candidate,
        source_name=source_name,
        asset_file_title=metadata.file_title,
    )

    try:
        download_image(
            metadata.file_title,
            download_url=metadata.download_url,
            destination=local_path,
            fixtures_dir=fixtures_dir,
        )
    except RuntimeError as error:
        stats.download_failure_count += 1
        errors.append(
            {
                "image_file_title": metadata.file_title,
                "source_name": source_name,
                "source_url": source_url,
                "error": str(error),
            }
        )
        return False

    stats.collected_count += 1
    collected_portrait_ids.add(portrait_id)
    records.append(
        PortraitRecord(
            portrait_id=portrait_id,
            source_name=source_name,
            entity_id=candidate.entity_id,
            person_name=candidate.person_name,
            birth_year=candidate.birth_year,
            year_basis="person_birth_year",
            era_name=era.era_name,
            birth_year_band=era.birth_year_band,
            nationality=country.country_name,
            gender=gender,
            source_url=source_url,
            media_page_url=metadata.media_page_url,
            image_file_title=metadata.file_title,
            license_short_name=metadata.license_short_name,
            license_url=metadata.license_url,
            usage_terms=metadata.usage_terms,
            artist=metadata.artist,
            credit=metadata.credit,
            local_path=str(local_path.relative_to(output_dir)),
        )
    )
    return True


def _maybe_collect_direct_asset(
    *,
    output_dir: Path,
    country: CountryTarget,
    era: EraDefinition,
    gender: str,
    asset_id: str,
    person_name: str,
    reference_year: int,
    year_basis: str,
    source_name: str,
    source_url: str,
    metadata: CommonsImageMetadata,
    stats: CombinationStats,
    records: list[PortraitRecord],
    errors: list[dict[str, str]],
    collected_portrait_ids: set[str],
    fixtures_dir: Path | None,
) -> bool:
    portrait_id = _portrait_id(asset_id, f"{source_name}:{metadata.file_title}")
    if portrait_id in collected_portrait_ids:
        return False

    if not is_commercially_usable(metadata):
        stats.license_rejected_count += 1
        return False

    asset_name = metadata.file_title.split(":", 1)[-1]
    suffix = Path(asset_name).suffix.lower() or ".jpg"
    stem = slugify(Path(asset_name).stem)[:80]
    local_path = (
        output_dir
        / "images"
        / country.country_code
        / f"{era.birth_year_start}_{era.birth_year_end}"
        / gender
        / f"{asset_id}_{slugify(source_name)}_{stem}{suffix}"
    )

    try:
        download_image(
            metadata.file_title,
            download_url=metadata.download_url,
            destination=local_path,
            fixtures_dir=fixtures_dir,
        )
    except RuntimeError as error:
        stats.download_failure_count += 1
        errors.append(
            {
                "image_file_title": metadata.file_title,
                "source_name": source_name,
                "source_url": source_url,
                "error": str(error),
            }
        )
        return False

    stats.collected_count += 1
    collected_portrait_ids.add(portrait_id)
    records.append(
        PortraitRecord(
            portrait_id=portrait_id,
            source_name=source_name,
            entity_id=asset_id,
            person_name=person_name,
            birth_year=reference_year,
            year_basis=year_basis,
            era_name=era.era_name,
            birth_year_band=era.birth_year_band,
            nationality=country.country_name,
            gender=gender,
            source_url=source_url,
            media_page_url=metadata.media_page_url,
            image_file_title=metadata.file_title,
            license_short_name=metadata.license_short_name,
            license_url=metadata.license_url,
            usage_terms=metadata.usage_terms,
            artist=metadata.artist,
            credit=metadata.credit,
            local_path=str(local_path.relative_to(output_dir)),
        )
    )
    return True
