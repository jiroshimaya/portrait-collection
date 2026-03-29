from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .axes import (
    DIRECT_SEARCH_GENDER_TERMS,
    CountryTarget,
    EraDefinition,
    country_query_variants,
    slugify,
)
from .commons import CommonsImageMetadata

CMA_SEARCH_ENDPOINT: Final[str] = (
    "https://openaccess-api.clevelandart.org/api/artworks/"
)
CMA_PAGE_SIZE: Final[int] = 100
USER_AGENT: Final[str] = (
    "portrait-collection/0.1 (https://github.com/jiroshimaya/portrait-collection)"
)
_LIVE_PAYLOAD_CACHE: dict[
    tuple[str, str], tuple[dict[str, Any] | None, str | None]
] = {}


@dataclass(frozen=True)
class CmaAsset:
    asset_id: str
    title: str
    year: int
    source_url: str
    metadata: CommonsImageMetadata


@dataclass(frozen=True)
class CmaSearchOutcome:
    assets: list[CmaAsset]
    errors: list[str]


def search_portraits_for_combo(
    country: CountryTarget,
    era: EraDefinition,
    gender: str,
    *,
    limit: int,
    fixtures_dir: Path | None = None,
) -> CmaSearchOutcome:
    results: list[CmaAsset] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    country_terms = country_query_variants(country.country_name)

    for country_term in country_terms:
        for term in DIRECT_SEARCH_GENDER_TERMS[gender]:
            payload, query_error = _load_payload(
                country=country,
                country_term=country_term,
                gender=gender,
                term=term,
                fixtures_dir=fixtures_dir,
            )
            if query_error is not None:
                errors.append(
                    "Cleveland Museum of Art search failed for "
                    f"{country.country_name} / {era.era_name} / {gender} / "
                    f"{country_term} / {term}: {query_error}"
                )
                continue
            if payload is None:
                continue

            for item in payload.get("data", []):
                if not _matches_country(item, country_terms):
                    continue
                asset = _build_asset(item=item, era=era)
                if asset is None or asset.asset_id in seen_ids:
                    continue
                seen_ids.add(asset.asset_id)
                results.append(asset)
                if len(results) >= limit:
                    return CmaSearchOutcome(assets=results, errors=errors)

    return CmaSearchOutcome(assets=results, errors=errors)


def _load_payload(
    *,
    country: CountryTarget,
    country_term: str,
    gender: str,
    term: str,
    fixtures_dir: Path | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if fixtures_dir is not None:
        fixture_path = (
            fixtures_dir
            / "cma"
            / (
                f"{country.country_code}_{gender}_{slugify(country_term)}_{slugify(term)}.json"
            )
        )
        if not fixture_path.exists():
            return {"data": []}, None
        with fixture_path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None

    return _load_live_payload(country_term=country_term, term=term)


def _load_live_payload(
    *, country_term: str, term: str
) -> tuple[dict[str, Any] | None, str | None]:
    cache_key = (country_term, term)
    if cache_key in _LIVE_PAYLOAD_CACHE:
        return _LIVE_PAYLOAD_CACHE[cache_key]

    query = quote(f"{country_term} {term}")
    url = f"{CMA_SEARCH_ENDPOINT}?q={query}&limit={CMA_PAGE_SIZE}"
    request = Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = (json.load(response), None)
    except (HTTPError, URLError, TimeoutError) as error:
        result = (None, str(error))

    _LIVE_PAYLOAD_CACHE[cache_key] = result
    return result


def _matches_country(item: dict[str, Any], country_terms: tuple[str, ...]) -> bool:
    culture = item.get("culture") or []
    haystacks = [
        " ".join(str(value) for value in culture if value),
        str(item.get("title") or ""),
        str(item.get("description") or ""),
        str(item.get("tombstone") or ""),
    ]
    joined = " ".join(haystacks).lower()
    return any(term.lower() in joined for term in country_terms)


def _build_asset(*, item: dict[str, Any], era: EraDefinition) -> CmaAsset | None:
    if str(item.get("share_license_status") or "").upper() != "CC0":
        return None

    year = _pick_reference_year(
        earliest=item.get("creation_date_earliest"),
        latest=item.get("creation_date_latest"),
        era=era,
    )
    if year is None:
        return None

    images = item.get("images", {})
    if not isinstance(images, dict):
        return None

    image_url = str(((images.get("web") or {}).get("url")) or "") or str(
        ((images.get("print") or {}).get("url")) or ""
    )
    if not image_url:
        return None

    object_id = int(item["id"])
    title = str(item.get("title") or f"Artwork {object_id}")
    source_url = str(item.get("url") or f"https://clevelandart.org/art/{object_id}")

    return CmaAsset(
        asset_id=str(object_id),
        title=title,
        year=year,
        source_url=source_url,
        metadata=CommonsImageMetadata(
            file_title=f"CMA:{object_id}_{slugify(title)}.jpg",
            download_url=image_url,
            media_page_url=source_url,
            license_short_name="CC0 / Public Domain",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            usage_terms="Cleveland Museum of Art Open Access",
            artist=str(item.get("tombstone") or ""),
            credit=title,
            attribution_required="false",
        ),
    )


def _pick_reference_year(
    *, earliest: Any, latest: Any, era: EraDefinition
) -> int | None:
    if not isinstance(earliest, int):
        return None
    latest_year = earliest if not isinstance(latest, int) else latest
    overlap_start = max(earliest, era.birth_year_start)
    overlap_end = min(latest_year, era.birth_year_end)
    if overlap_start > overlap_end:
        return None
    return overlap_start
