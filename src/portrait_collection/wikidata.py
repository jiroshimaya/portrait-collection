from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from .axes import CountryTarget

WIKIDATA_SPARQL_ENDPOINT: Final[str] = "https://query.wikidata.org/sparql"
USER_AGENT: Final[str] = (
    "portrait-collection/0.1 (https://github.com/jiroshimaya/portrait-collection)"
)
GENDER_QIDS: Final[dict[str, str]] = {
    "male": "Q6581097",
    "female": "Q6581072",
}


@dataclass(frozen=True)
class WikidataCandidate:
    entity_id: str
    person_name: str
    birth_year: int
    gender: str
    country_name: str
    country_qid: str
    image_file_title: str
    wikidata_url: str


def fetch_candidates(
    country: CountryTarget,
    *,
    gender: str,
    limit: int,
    sort_order: str,
    fixtures_dir: Path | None = None,
) -> list[WikidataCandidate]:
    payload = _load_payload(
        country=country,
        gender=gender,
        limit=limit,
        sort_order=sort_order,
        fixtures_dir=fixtures_dir,
    )
    bindings = payload["results"]["bindings"]
    candidates: list[WikidataCandidate] = []
    seen_keys: set[tuple[str, str]] = set()

    for binding in bindings:
        entity_url = binding["person"]["value"]
        entity_id = entity_url.rsplit("/", 1)[-1]
        birth_year = _extract_birth_year(binding)
        if birth_year is None:
            continue
        image_url = binding["image"]["value"]
        image_file_title = "File:" + unquote(
            urlparse(image_url).path.rsplit("/", 1)[-1]
        )
        key = (entity_id, image_file_title)

        if key in seen_keys:
            continue

        seen_keys.add(key)
        candidates.append(
            WikidataCandidate(
                entity_id=entity_id,
                person_name=binding["personLabel"]["value"],
                birth_year=birth_year,
                gender=binding["genderLabel"]["value"],
                country_name=binding["countryLabel"]["value"],
                country_qid=country.wikidata_qid,
                image_file_title=image_file_title,
                wikidata_url=entity_url,
            )
        )

    candidates.sort(key=lambda candidate: (candidate.birth_year, candidate.person_name))
    return candidates


def _load_payload(
    country: CountryTarget,
    gender: str,
    limit: int,
    sort_order: str,
    fixtures_dir: Path | None,
) -> dict[str, Any]:
    if fixtures_dir is not None:
        fixture_path = (
            fixtures_dir
            / "wikidata"
            / f"{country.wikidata_qid}_{gender}_{sort_order}.json"
        )

        with fixture_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    query = _build_query(
        country_qid=country.wikidata_qid,
        gender=gender,
        limit=limit,
        sort_order=sort_order,
    )
    url = f"{WIKIDATA_SPARQL_ENDPOINT}?format=json&query={quote(query)}"
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )

    for attempt in range(1):
        try:
            with urlopen(request, timeout=12) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 0:
                raise RuntimeError(
                    f"Wikidata query failed for {country.country_name} / {gender} / {sort_order}: {error}"
                ) from error
        except (URLError, TimeoutError) as error:
            if attempt == 0:
                raise RuntimeError(
                    f"Wikidata query failed for {country.country_name} / {gender} / {sort_order}: {error}"
                ) from error
        time.sleep(2**attempt)

    raise RuntimeError(
        f"Wikidata query failed for {country.country_name} / {gender} / {sort_order}"
    )


def _build_query(
    *,
    country_qid: str,
    gender: str,
    limit: int,
    sort_order: str,
) -> str:
    order_direction = "ASC" if sort_order == "asc" else "DESC"
    return f"""
SELECT DISTINCT ?person ?personLabel ?dateOfBirth ?genderLabel ?countryLabel ?image WHERE {{
  BIND(wd:{country_qid} AS ?country)
  ?person wdt:P31 wd:Q5 ;
          wdt:P18 ?image ;
          wdt:P569 ?dateOfBirth ;
          wdt:P21 ?gender .
  BIND(YEAR(?dateOfBirth) AS ?birthYear)
  FILTER(?gender = wd:{GENDER_QIDS[gender]})
  ?person wdt:P19 ?birthPlace .
  ?birthPlace wdt:P17 ?country .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
ORDER BY {order_direction}(?dateOfBirth) ?personLabel
LIMIT {limit}
""".strip()


def _extract_birth_year(binding: dict[str, Any]) -> int | None:
    if "birthYear" in binding:
        try:
            return int(binding["birthYear"]["value"])
        except (KeyError, TypeError, ValueError):
            pass

    date_of_birth = binding.get("dateOfBirth", {}).get("value", "")
    match = re.match(r"^([+-]?\d+)", str(date_of_birth))
    if match is None:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None
