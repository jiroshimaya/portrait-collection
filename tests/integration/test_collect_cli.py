from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from urllib.parse import quote


class TestCollectCli:
    def test_正常系_fixture指定で画像とメタデータを保存する(
        self, tmp_path: Path
    ) -> None:
        fixtures_dir = tmp_path / "fixtures"
        (fixtures_dir / "wikidata").mkdir(parents=True)
        (fixtures_dir / "commons").mkdir(parents=True)
        (fixtures_dir / "met_search").mkdir(parents=True)
        (fixtures_dir / "met_objects").mkdir(parents=True)
        (fixtures_dir / "binary").mkdir(parents=True)
        output_dir = tmp_path / "output"
        eras_file = tmp_path / "eras.csv"
        countries_file = tmp_path / "countries.csv"

        eras_file.write_text(
            "\n".join(
                [
                    "era_name,birth_year_band,birth_year_start,birth_year_end",
                    "近代後期,1850–1899,1850,1899",
                ]
            ),
            encoding="utf-8",
        )
        countries_file.write_text(
            "\n".join(
                [
                    "country_code,country_name,wikidata_qid",
                    "greece,Greece,Q41",
                ]
            ),
            encoding="utf-8",
        )

        file_title = "File:Hypatia portrait.jpg"
        (fixtures_dir / "wikidata" / "Q41_female_asc.json").write_text(
            json.dumps(
                {
                    "results": {
                        "bindings": [
                            {
                                "person": {
                                    "value": "https://www.wikidata.org/entity/Q123"
                                },
                                "personLabel": {"value": "Example Scientist"},
                                "dateOfBirth": {"value": "1867-11-07T00:00:00Z"},
                                "birthYear": {"value": "1867"},
                                "genderLabel": {"value": "female"},
                                "countryLabel": {"value": "Greece"},
                                "image": {
                                    "value": "http://commons.wikimedia.org/wiki/Special:FilePath/Hypatia%20portrait.jpg"
                                },
                            }
                        ]
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (fixtures_dir / "wikidata" / "Q41_female_desc.json").write_text(
            json.dumps({"results": {"bindings": []}}, ensure_ascii=False),
            encoding="utf-8",
        )
        (fixtures_dir / "wikidata" / "Q41_male_asc.json").write_text(
            json.dumps({"results": {"bindings": []}}, ensure_ascii=False),
            encoding="utf-8",
        )
        (fixtures_dir / "wikidata" / "Q41_male_desc.json").write_text(
            json.dumps({"results": {"bindings": []}}, ensure_ascii=False),
            encoding="utf-8",
        )
        (fixtures_dir / "commons" / f"{quote(file_title, safe='')}.json").write_text(
            json.dumps(
                {
                    "query": {
                        "pages": {
                            "1": {
                                "imageinfo": [
                                    {
                                        "url": "https://upload.wikimedia.org/example.jpg",
                                        "thumburl": "https://upload.wikimedia.org/example-512.jpg",
                                        "extmetadata": {
                                            "LicenseShortName": {
                                                "value": "CC BY-NC 4.0"
                                            },
                                            "LicenseUrl": {
                                                "value": "https://creativecommons.org/licenses/by-nc/4.0/"
                                            },
                                            "UsageTerms": {
                                                "value": "Creative Commons Attribution-NonCommercial 4.0"
                                            },
                                            "Artist": {"value": "Example Artist"},
                                            "Credit": {"value": "Example Credit"},
                                            "AttributionRequired": {"value": "true"},
                                        },
                                    }
                                ]
                            }
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (fixtures_dir / "binary" / quote(file_title, safe="")).write_bytes(
            b"fake-image-binary"
        )
        (fixtures_dir / "met_search" / "example-scientist.json").write_text(
            json.dumps({"objectIDs": [1001]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (fixtures_dir / "met_objects" / "1001.json").write_text(
            json.dumps(
                {
                    "objectID": 1001,
                    "title": "Portrait of Example Scientist",
                    "isPublicDomain": True,
                    "primaryImageSmall": "https://images.metmuseum.org/example-scientist.jpg",
                    "objectURL": "https://www.metmuseum.org/art/collection/search/1001",
                    "artistDisplayName": "Example Sculptor",
                    "creditLine": "Open Access credit",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (
            fixtures_dir
            / "binary"
            / quote("MetObject:1001_portrait-of-example-scientist.jpg", safe="")
        ).write_bytes(b"fake-met-image-binary")

        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "portrait_collection.cli",
                "collect",
                "--output-dir",
                str(output_dir),
                "--per-combination-target",
                "1",
                "--eras-file",
                str(eras_file),
                "--countries-file",
                str(countries_file),
                "--fixtures-dir",
                str(fixtures_dir),
            ],
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[2],
            check=False,
        )

        assert result.returncode == 0
        assert "収集完了: 1 件保存" in result.stdout
        assert (output_dir / "metadata" / "portraits.jsonl").exists()
        assert (output_dir / "metadata" / "collection_summary.csv").exists()

        records = (
            (output_dir / "metadata" / "portraits.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert len(records) == 1
        record = json.loads(records[0])
        assert record["nationality"] == "Greece"
        assert record["gender"] == "female"
        assert record["source_name"] == "the-met"

        with (output_dir / "metadata" / "collection_summary.csv").open(
            "r", encoding="utf-8"
        ) as handle:
            summary_rows = list(csv.DictReader(handle))

        assert summary_rows == [
            {
                "nationality": "Greece",
                "era_name": "近代後期",
                "birth_year_band": "1850–1899",
                "gender": "male",
                "target_count": "1",
                "collected_count": "0",
                "candidate_count": "0",
                "license_rejected_count": "0",
                "download_failure_count": "0",
                "shortage_reason": "Wikidata 上で候補が見つからなかった",
            },
            {
                "nationality": "Greece",
                "era_name": "近代後期",
                "birth_year_band": "1850–1899",
                "gender": "female",
                "target_count": "1",
                "collected_count": "1",
                "candidate_count": "1",
                "license_rejected_count": "1",
                "download_failure_count": "0",
                "shortage_reason": "",
            },
        ]

    def test_正常系_artic直検索で不足分を補完できる(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path / "fixtures"
        (fixtures_dir / "wikidata").mkdir(parents=True)
        (fixtures_dir / "commons").mkdir(parents=True)
        (fixtures_dir / "met_search").mkdir(parents=True)
        (fixtures_dir / "met_objects").mkdir(parents=True)
        (fixtures_dir / "artic").mkdir(parents=True)
        (fixtures_dir / "binary").mkdir(parents=True)
        output_dir = tmp_path / "output"
        eras_file = tmp_path / "eras.csv"
        countries_file = tmp_path / "countries.csv"

        eras_file.write_text(
            "\n".join(
                [
                    "era_name,birth_year_band,birth_year_start,birth_year_end",
                    "近代後期,1850–1899,1850,1899",
                ]
            ),
            encoding="utf-8",
        )
        countries_file.write_text(
            "\n".join(
                [
                    "country_code,country_name,wikidata_qid",
                    "japan,Japan,Q17",
                ]
            ),
            encoding="utf-8",
        )

        for name in (
            "Q17_female_asc.json",
            "Q17_female_desc.json",
            "Q17_male_asc.json",
            "Q17_male_desc.json",
        ):
            (fixtures_dir / "wikidata" / name).write_text(
                json.dumps({"results": {"bindings": []}}, ensure_ascii=False),
                encoding="utf-8",
            )

        (fixtures_dir / "artic" / "japan_female_japan_portrait-woman.json").write_text(
            json.dumps(
                {
                    "data": [
                        {
                            "id": 3001,
                            "title": "Portrait of a Japanese Woman",
                            "date_start": 1888,
                            "date_end": 1888,
                            "image_id": "artic-image-3001",
                            "is_public_domain": True,
                            "artist_display": "Japanese artist",
                            "place_of_origin": "Japan",
                        }
                    ],
                    "config": {
                        "website_url": "https://www.artic.edu",
                        "iiif_url": "https://www.artic.edu/iiif/2",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (
            fixtures_dir
            / "binary"
            / quote("AIC:3001_portrait-of-a-japanese-woman.jpg", safe="")
        ).write_bytes(b"fake-artic-image-binary")

        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "portrait_collection.cli",
                "collect",
                "--output-dir",
                str(output_dir),
                "--per-combination-target",
                "1",
                "--eras-file",
                str(eras_file),
                "--countries-file",
                str(countries_file),
                "--fixtures-dir",
                str(fixtures_dir),
            ],
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[2],
            check=False,
        )

        assert result.returncode == 0
        records = (
            (output_dir / "metadata" / "portraits.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert len(records) == 1
        record = json.loads(records[0])
        assert record["source_name"] == "art-institute-of-chicago"
        assert record["nationality"] == "Japan"
        assert record["gender"] == "female"

    def test_正常系_wellcome直検索で不足分を補完できる(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path / "fixtures"
        (fixtures_dir / "wikidata").mkdir(parents=True)
        (fixtures_dir / "commons").mkdir(parents=True)
        (fixtures_dir / "met_search").mkdir(parents=True)
        (fixtures_dir / "met_objects").mkdir(parents=True)
        (fixtures_dir / "artic").mkdir(parents=True)
        (fixtures_dir / "cma").mkdir(parents=True)
        (fixtures_dir / "wellcome").mkdir(parents=True)
        (fixtures_dir / "binary").mkdir(parents=True)
        output_dir = tmp_path / "output"
        eras_file = tmp_path / "eras.csv"
        countries_file = tmp_path / "countries.csv"

        eras_file.write_text(
            "\n".join(
                [
                    "era_name,birth_year_band,birth_year_start,birth_year_end",
                    "近代後期,1850–1899,1850,1899",
                ]
            ),
            encoding="utf-8",
        )
        countries_file.write_text(
            "\n".join(
                [
                    "country_code,country_name,wikidata_qid",
                    "japan,Japan,Q17",
                ]
            ),
            encoding="utf-8",
        )

        for name in (
            "Q17_female_asc.json",
            "Q17_female_desc.json",
            "Q17_male_asc.json",
            "Q17_male_desc.json",
        ):
            (fixtures_dir / "wikidata" / name).write_text(
                json.dumps({"results": {"bindings": []}}, ensure_ascii=False),
                encoding="utf-8",
            )

        (
            fixtures_dir / "wellcome" / "japan_female_japan_portrait-woman_p1.json"
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
        (
            fixtures_dir
            / "binary"
            / quote(
                "Wellcome:ww7n5upn_a-japanese-married-woman-wearing-traditional-dress-coloured-photograph-by-felice-beato-ca-1870.jpg",
                safe="",
            )
        ).write_bytes(b"fake-wellcome-image-binary")

        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "portrait_collection.cli",
                "collect",
                "--output-dir",
                str(output_dir),
                "--per-combination-target",
                "1",
                "--eras-file",
                str(eras_file),
                "--countries-file",
                str(countries_file),
                "--fixtures-dir",
                str(fixtures_dir),
            ],
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[2],
            check=False,
        )

        assert result.returncode == 0
        record = json.loads(
            (output_dir / "metadata" / "portraits.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        assert record["source_name"] == "wellcome-collection"
