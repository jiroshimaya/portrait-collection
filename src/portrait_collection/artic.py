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

ARTIC_SEARCH_ENDPOINT: Final[str] = "https://api.artic.edu/api/v1/artworks/search"
ARTIC_WEBSITE_URL: Final[str] = "https://www.artic.edu"
ARTIC_IIIF_URL: Final[str] = "https://www.artic.edu/iiif/2"
ARTIC_PAGE_SIZE: Final[int] = 100
USER_AGENT: Final[str] = (
    "portrait-collection/0.1 (https://github.com/jiroshimaya/portrait-collection)"
)
_LIVE_PAYLOAD_CACHE: dict[
    tuple[str, str], tuple[dict[str, Any] | None, str | None]
] = {}


@dataclass(frozen=True)
class ArticAsset:
    asset_id: str
    title: str
    year: int
    source_url: str
    metadata: CommonsImageMetadata


@dataclass(frozen=True)
class ArticSearchOutcome:
    assets: list[ArticAsset]
    errors: list[str]


def search_portraits_for_combo(
    country: CountryTarget,
    era: EraDefinition,
    gender: str,
    *,
    limit: int,
    fixtures_dir: Path | None = None,
) -> ArticSearchOutcome:
    results: list[ArticAsset] = []
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
                    "Art Institute of Chicago search failed for "
                    f"{country.country_name} / {era.era_name} / {gender} / "
                    f"{country_term} / {term}: {query_error}"
                )
                continue
            if payload is None:
                continue

            config = payload.get("config", {})
            for item in payload.get("data", []):
                if not _matches_country(item, country_terms):
                    continue
                asset = _build_asset(item=item, config=config, era=era)
                if asset is None or asset.asset_id in seen_ids:
                    continue
                seen_ids.add(asset.asset_id)
                results.append(asset)
                if len(results) >= limit:
                    return ArticSearchOutcome(assets=results, errors=errors)

    return ArticSearchOutcome(assets=results, errors=errors)


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
            / "artic"
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
    fields = quote(
        "id,title,date_start,date_end,image_id,is_public_domain,"
        "artist_display,place_of_origin,thumbnail"
    )
    url = f"{ARTIC_SEARCH_ENDPOINT}?q={query}&limit={ARTIC_PAGE_SIZE}&fields={fields}"
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
    haystacks = [
        str(item.get("place_of_origin") or ""),
        str(item.get("artist_display") or ""),
        str(item.get("title") or ""),
    ]
    joined = " ".join(haystacks).lower()
    return any(term.lower() in joined for term in country_terms)


def _build_asset(
    *, item: dict[str, Any], config: dict[str, Any], era: EraDefinition
) -> ArticAsset | None:
    if not item.get("is_public_domain"):
        return None

    image_id = str(item.get("image_id") or "")
    if not image_id:
        return None

    year = _pick_reference_year(
        date_start=item.get("date_start"),
        date_end=item.get("date_end"),
        era=era,
    )
    if year is None:
        return None

    object_id = int(item["id"])
    title = str(item.get("title") or f"Artwork {object_id}")
    website_url = str(config.get("website_url") or ARTIC_WEBSITE_URL).rstrip("/")
    iiif_url = str(config.get("iiif_url") or ARTIC_IIIF_URL).rstrip("/")
    source_url = f"{website_url}/artworks/{object_id}"

    return ArticAsset(
        asset_id=str(object_id),
        title=title,
        year=year,
        source_url=source_url,
        metadata=CommonsImageMetadata(
            file_title=f"AIC:{object_id}_{slugify(title)}.jpg",
            download_url=f"{iiif_url}/{image_id}/full/843,/0/default.jpg",
            media_page_url=source_url,
            license_short_name="CC0 / Public Domain",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            usage_terms="Art Institute of Chicago public domain",
            artist=str(item.get("artist_display") or ""),
            credit=title,
            attribution_required="false",
        ),
    )


def _pick_reference_year(
    *, date_start: Any, date_end: Any, era: EraDefinition
) -> int | None:
    if not isinstance(date_start, int):
        return None
    end_year = date_start if not isinstance(date_end, int) else date_end
    overlap_start = max(date_start, era.birth_year_start)
    overlap_end = min(end_year, era.birth_year_end)
    if overlap_start > overlap_end:
        return None
    return overlap_start
