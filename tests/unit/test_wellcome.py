from __future__ import annotations

import json
from pathlib import Path

from portrait_collection.axes import CountryTarget, EraDefinition
from portrait_collection.wellcome import search_portraits_for_combo


class TestWellcomeSearch:
    def test_正常系_公開ドメインのサムネイルを年代付きで取得できる(
        self, tmp_path: Path
    ) -> None:
        fixtures_dir = tmp_path
        (fixtures_dir / "wellcome").mkdir()
        (
            fixtures_dir / "wellcome" / "japan_female_japanese_portrait-woman_p1.json"
        ).write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "id": "ww7n5upn",
                            "title": "A Japanese married woman wearing traditional dress. Coloured photograph by Felice Beato, ca. 1870.",
                            "lettering": "Japanese married lady",
                            "thumbnail": {
                                "url": "https://iiif.wellcomecollection.org/image/V0037655/full/300,/0/default.jpg",
                                "license": {
                                    "label": "Public Domain Mark",
                                    "url": "https://creativecommons.org/share-your-work/public-domain/pdm/",
                                },
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        outcome = search_portraits_for_combo(
            CountryTarget("japan", "Japan", "Q17"),
            EraDefinition("近代後期", "1850–1899", 1850, 1899),
            "female",
            limit=1,
            fixtures_dir=fixtures_dir,
        )

        assert outcome.errors == []
        assert len(outcome.assets) == 1
        assert outcome.assets[0].asset_id == "ww7n5upn"
        assert "/full/843,/0/default.jpg" in outcome.assets[0].metadata.download_url
