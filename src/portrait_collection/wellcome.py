from __future__ import annotations

import json
import re
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

WELLCOME_SEARCH_ENDPOINT: Final[str] = (
    "https://api.wellcomecollection.org/catalogue/v2/works"
)
WELLCOME_PAGE_SIZE: Final[int] = 50
WELLCOME_MAX_PAGES: Final[int] = 2
USER_AGENT: Final[str] = (
    "portrait-collection/0.1 (https://github.com/jiroshimaya/portrait-collection)"
)
_LIVE_PAYLOAD_CACHE: dict[
    tuple[str, str, int], tuple[dict[str, Any] | None, str | None]
] = {}


@dataclass(frozen=True)
class WellcomeAsset:
    asset_id: str
    title: str
    year: int
    source_url: str
    metadata: CommonsImageMetadata


@dataclass(frozen=True)
class WellcomeSearchOutcome:
    assets: list[WellcomeAsset]
    errors: list[str]


def search_portraits_for_combo(
    country: CountryTarget,
    era: EraDefinition,
    gender: str,
    *,
    limit: int,
    fixtures_dir: Path | None = None,
) -> WellcomeSearchOutcome:
    results: list[WellcomeAsset] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    country_terms = country_query_variants(country.country_name)

    for country_term in country_terms:
        for term in DIRECT_SEARCH_GENDER_TERMS[gender]:
            for page in range(1, WELLCOME_MAX_PAGES + 1):
                payload, query_error = _load_payload(
                    country=country,
                    country_term=country_term,
                    gender=gender,
                    term=term,
                    page=page,
                    fixtures_dir=fixtures_dir,
                )
                if query_error is not None:
                    errors.append(
                        "Wellcome Collection search failed for "
                        f"{country.country_name} / {era.era_name} / {gender} / "
                        f"{country_term} / {term} / page {page}: {query_error}"
                    )
                    break
                if payload is None:
                    break

                entries = payload.get("results", [])
                if not isinstance(entries, list) or not entries:
                    break
                for item in entries:
                    if not _matches_country(item, country_terms):
                        continue
                    asset = _build_asset(item=item, era=era)
                    if asset is None or asset.asset_id in seen_ids:
                        continue
                    seen_ids.add(asset.asset_id)
                    results.append(asset)
                    if len(results) >= limit:
                        return WellcomeSearchOutcome(assets=results, errors=errors)
                if len(entries) < WELLCOME_PAGE_SIZE:
                    break

    return WellcomeSearchOutcome(assets=results, errors=errors)


def _load_payload(
    *,
    country: CountryTarget,
    country_term: str,
    gender: str,
    term: str,
    page: int,
    fixtures_dir: Path | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if fixtures_dir is not None:
        fixture_path = (
            fixtures_dir
            / "wellcome"
            / (
                f"{country.country_code}_{gender}_{slugify(country_term)}_"
                f"{slugify(term)}_p{page}.json"
            )
        )
        if not fixture_path.exists():
            return {"results": []}, None
        with fixture_path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None

    return _load_live_payload(country_term=country_term, term=term, page=page)


def _load_live_payload(
    *, country_term: str, term: str, page: int
) -> tuple[dict[str, Any] | None, str | None]:
    cache_key = (country_term, term, page)
    if cache_key in _LIVE_PAYLOAD_CACHE:
        return _LIVE_PAYLOAD_CACHE[cache_key]

    query = quote(f"{country_term} {term}")
    url = (
        f"{WELLCOME_SEARCH_ENDPOINT}?query={query}&pageSize={WELLCOME_PAGE_SIZE}"
        f"&include=images&page={page}"
    )
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
        str(item.get("title") or ""),
        str(item.get("lettering") or ""),
        str(item.get("physicalDescription") or ""),
    ]
    joined = " ".join(haystacks).lower()
    return any(term.lower() in joined for term in country_terms)


def _build_asset(*, item: dict[str, Any], era: EraDefinition) -> WellcomeAsset | None:
    thumbnail = item.get("thumbnail")
    if not isinstance(thumbnail, dict):
        return None
    license_info = thumbnail.get("license")
    if not isinstance(license_info, dict):
        return None
    license_label = str(license_info.get("label") or "")
    if "public domain" not in license_label.lower():
        return None

    image_url = str(thumbnail.get("url") or "")
    if not image_url:
        return None
    image_url = re.sub(
        r"/full/\d+,/0/default\.jpg$", "/full/843,/0/default.jpg", image_url
    )

    year = _extract_year(item)
    if year is None or not (era.birth_year_start <= year <= era.birth_year_end):
        return None

    work_id = str(item.get("id") or "")
    if not work_id:
        return None
    title = str(item.get("title") or work_id)
    source_url = f"https://wellcomecollection.org/works/{work_id}"

    return WellcomeAsset(
        asset_id=work_id,
        title=title,
        year=year,
        source_url=source_url,
        metadata=CommonsImageMetadata(
            file_title=f"Wellcome:{work_id}_{slugify(title)}.jpg",
            download_url=image_url,
            media_page_url=source_url,
            license_short_name=license_label or "Public Domain Mark",
            license_url=str(license_info.get("url") or ""),
            usage_terms="Wellcome Collection public-domain thumbnail",
            artist=str(item.get("lettering") or ""),
            credit=title,
            attribution_required="false",
        ),
    )


def _extract_year(item: dict[str, Any]) -> int | None:
    candidates = [
        item.get("title"),
        item.get("lettering"),
        item.get("physicalDescription"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        match = re.search(r"([12]\d{3})", str(candidate))
        if match is None:
            continue
        return int(match.group(1))
    return None
