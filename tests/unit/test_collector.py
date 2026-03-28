from __future__ import annotations

from portrait_collection.commons import CommonsImageMetadata, is_commercially_usable


class TestCommercialLicenseFilter:
    def test_正常系_cc_by_saを商用利用可能として扱う(self) -> None:
        metadata = CommonsImageMetadata(
            file_title="File:Example.jpg",
            download_url="https://example.com/image.jpg",
            media_page_url="https://commons.wikimedia.org/wiki/File:Example.jpg",
            license_short_name="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            usage_terms="Creative Commons Attribution-Share Alike 4.0",
            artist="Author",
            credit="Credit",
            attribution_required="true",
        )

        assert is_commercially_usable(metadata) is True

    def test_異常系_noncommercialを商用利用不可として除外する(self) -> None:
        metadata = CommonsImageMetadata(
            file_title="File:Example.jpg",
            download_url="https://example.com/image.jpg",
            media_page_url="https://commons.wikimedia.org/wiki/File:Example.jpg",
            license_short_name="CC BY-NC 4.0",
            license_url="https://creativecommons.org/licenses/by-nc/4.0/",
            usage_terms="Creative Commons Attribution-NonCommercial 4.0",
            artist="Author",
            credit="Credit",
            attribution_required="true",
        )

        assert is_commercially_usable(metadata) is False
