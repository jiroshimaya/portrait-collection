from __future__ import annotations

import io
import json
from pathlib import Path

from portrait_collection import loc
from portrait_collection.axes import CountryTarget, EraDefinition
from portrait_collection.loc import search_portraits_for_combo


class TestLocSearch:
    def test_正常系_国名バリエーションで結果を取得できる(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path
        (fixtures_dir / "loc").mkdir()

        country = CountryTarget(
            country_code="japan", country_name="Japan", wikidata_qid="Q17"
        )
        era = EraDefinition(
            era_name="近代後期",
            birth_year_band="1850–1899",
            birth_year_start=1850,
            birth_year_end=1899,
        )

        (
            fixtures_dir / "loc" / "japan_1850_1899_female_japanese_portrait-woman.json"
        ).write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "url": "https://www.loc.gov/item/jp-portrait-1/",
                            "title": "Portrait of a Japanese woman",
                            "date": "1875",
                            "rights_advisory": "No known restrictions.",
                            "image_url": [
                                "https://cdn.loc.gov/jp-portrait-1.jpg",
                                "https://cdn.loc.gov/jp-portrait-1_v.jpg",
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        outcome = search_portraits_for_combo(
            country,
            era,
            "female",
            limit=1,
            fixtures_dir=fixtures_dir,
        )

        assert len(outcome.assets) == 1
        assert outcome.assets[0].asset_id == "jp-portrait-1"
        assert outcome.assets[0].metadata.download_url.endswith("_v.jpg")
        assert outcome.errors == []

    def test_正常系_ページ送りで後続ページの候補を取得できる(
        self, tmp_path: Path
    ) -> None:
        fixtures_dir = tmp_path
        (fixtures_dir / "loc").mkdir()

        country = CountryTarget(
            country_code="japan", country_name="Japan", wikidata_qid="Q17"
        )
        era = EraDefinition(
            era_name="近代後期",
            birth_year_band="1850–1899",
            birth_year_start=1850,
            birth_year_end=1899,
        )

        page1_items = [
            {
                "url": f"https://www.loc.gov/item/jp-old-{index}/",
                "title": f"Old portrait {index}",
                "date": "1700",
                "rights_advisory": "No known restrictions.",
                "image_url": [f"https://cdn.loc.gov/jp-old-{index}.jpg"],
            }
            for index in range(100)
        ]
        (
            fixtures_dir / "loc" / "japan_1850_1899_female_portrait-woman.json"
        ).write_text(
            json.dumps({"results": page1_items}, ensure_ascii=False),
            encoding="utf-8",
        )
        (
            fixtures_dir / "loc" / "japan_1850_1899_female_japan_portrait-woman_p2.json"
        ).write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "url": "https://www.loc.gov/item/jp-page-2/",
                            "title": "Portrait discovered on page 2",
                            "date": "1888",
                            "rights_advisory": "No known restrictions.",
                            "image_url": ["https://cdn.loc.gov/jp-page-2.jpg"],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        outcome = search_portraits_for_combo(
            country,
            era,
            "female",
            limit=1,
            fixtures_dir=fixtures_dir,
        )

        assert len(outcome.assets) == 1
        assert outcome.assets[0].asset_id == "jp-page-2"
        assert outcome.errors == []

    def test_正常系_同一LoCクエリ結果を時代またぎで再利用する(
        self, monkeypatch
    ) -> None:
        loc._LIVE_PAYLOAD_CACHE.clear()
        calls: list[str] = []

        class FakeResponse(io.BytesIO):
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        def fake_urlopen(request, timeout: int):
            del timeout
            calls.append(request.full_url)
            payload = {
                "results": [
                    {
                        "url": "https://www.loc.gov/item/jp-cache-1/",
                        "title": "Cached portrait",
                        "date": "1875",
                        "rights_advisory": "No known restrictions.",
                        "image_url": ["https://cdn.loc.gov/jp-cache-1.jpg"],
                    }
                ]
            }
            return FakeResponse(json.dumps(payload).encode("utf-8"))

        monkeypatch.setattr(loc, "urlopen", fake_urlopen)

        country = CountryTarget(
            country_code="japan", country_name="Japan", wikidata_qid="Q17"
        )
        era_1 = EraDefinition(
            era_name="近代後期",
            birth_year_band="1850–1899",
            birth_year_start=1850,
            birth_year_end=1899,
        )
        era_2 = EraDefinition(
            era_name="現代前期",
            birth_year_band="1900–1949",
            birth_year_start=1900,
            birth_year_end=1949,
        )

        first = search_portraits_for_combo(country, era_1, "female", limit=1)
        second = search_portraits_for_combo(country, era_2, "female", limit=1)

        assert len(first.assets) == 1
        assert len(second.assets) == 0
        assert (
            calls.count(
                "https://www.loc.gov/photos/?fo=json&sp=1&c=100&q=Japan%20portrait%20woman"
            )
            == 1
        )

    def test_正常系_一部クエリ失敗でも他の検索語で回収を継続する(
        self, monkeypatch
    ) -> None:
        country = CountryTarget(
            country_code="japan", country_name="Japan", wikidata_qid="Q17"
        )
        era = EraDefinition(
            era_name="近代後期",
            birth_year_band="1850–1899",
            birth_year_start=1850,
            birth_year_end=1899,
        )

        def fake_load_payload(
            *, country, country_term, era, gender, term, page, fixtures_dir
        ):
            del country, era, gender, fixtures_dir
            if country_term == "Japan" and term == "portrait woman" and page == 1:
                return None, "HTTP Error 429: Too Many Requests"
            if country_term == "Japanese" and term == "portrait woman" and page == 1:
                return (
                    {
                        "results": [
                            {
                                "url": "https://www.loc.gov/item/jp-fallback-1/",
                                "title": "Fallback portrait",
                                "date": "1882",
                                "rights_advisory": "No known restrictions.",
                                "image_url": ["https://cdn.loc.gov/jp-fallback-1.jpg"],
                            }
                        ]
                    },
                    None,
                )
            return {"results": []}, None

        monkeypatch.setattr(loc, "_load_payload", fake_load_payload)

        outcome = search_portraits_for_combo(country, era, "female", limit=1)

        assert len(outcome.assets) == 1
        assert outcome.assets[0].asset_id == "jp-fallback-1"
        assert len(outcome.errors) == 1
        assert "HTTP Error 429" in outcome.errors[0]
