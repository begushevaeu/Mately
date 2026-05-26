from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
from zipfile import ZipFile

import pytest

from app.models import Comment, ContentItem, Couple, PlaceComment, PlaceItem, PlaceRating, Rating
from app.services.exports import (
    CONTENT_EXPORT_COLUMNS,
    PLACES_EXPORT_COLUMNS,
    CoupleExportService,
    build_content_csv,
    build_places_csv,
)


@dataclass(slots=True)
class FakeContentRepository:
    items: list[ContentItem]

    async def list_for_couple(self, couple_id: int) -> list[ContentItem]:
        return [item for item in self.items if item.couple_id == couple_id]


@dataclass(slots=True)
class FakePlaceRepository:
    items: list[PlaceItem]

    async def list_for_couple(self, couple_id: int) -> list[PlaceItem]:
        return [item for item in self.items if item.couple_id == couple_id]


def read_csv_rows(value: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(value)))


def test_content_export_csv_contains_completed_and_long_list_rows_without_ids() -> None:
    completed = ContentItem(
        id=1,
        couple_id=1,
        title="Movie <3",
        category="MOVIE",
        added_by=100,
        status="COMPLETED",
        completed_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
    )
    completed.ratings = [
        Rating(content_id=1, user_id=100, score=9, emoji="heart", response="RATED"),
        Rating(content_id=1, user_id=200, score=None, emoji=None, response="NOT_ACQUAINTED"),
    ]
    completed.comments = [Comment(content_id=1, user_id=100, text="secret")]
    planned = ContentItem(id=2, couple_id=1, title="Book", category="BOOK", added_by=100, status="NOT_COMPLETED")
    planned.ratings = []
    planned.comments = []

    csv_text = build_content_csv([completed, planned], "Europe/Moscow")
    rows = read_csv_rows(csv_text)

    assert rows[0] == {
        "title": "Movie <3",
        "category": "MOVIE",
        "status": "COMPLETED",
        "completed_at": "2026-05-20 13:00",
        "average_rating": "9.0",
        "reactions": "heart",
        "comments_count": "1",
    }
    assert rows[1]["status"] == "NOT_COMPLETED"
    assert rows[1]["title"] == "Book"
    assert "id" not in rows[0]
    assert "secret" not in csv_text


def test_places_export_csv_contains_visited_and_long_list_rows_without_comments() -> None:
    visited = PlaceItem(
        id=1,
        couple_id=1,
        title="Sage",
        category="RESTAURANT",
        added_by=100,
        status="VISITED",
        visited_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
    )
    visited.ratings = [
        PlaceRating(place_id=1, user_id=100, score=10, response="RATED"),
        PlaceRating(place_id=1, user_id=200, score=None, response="NOT_ACQUAINTED"),
    ]
    visited.comments = [PlaceComment(place_id=1, user_id=100, text="private note")]
    planned = PlaceItem(id=2, couple_id=1, title="Park", category="PARK", added_by=100, status="NOT_VISITED")
    planned.ratings = []
    planned.comments = []

    csv_text = build_places_csv([visited, planned], "Europe/Moscow")
    rows = read_csv_rows(csv_text)

    assert rows[0] == {
        "title": "Sage",
        "category": "RESTAURANT",
        "status": "VISITED",
        "visited_at": "2026-05-20 13:00",
        "average_rating": "10.0",
        "comments_count": "1",
        "not_acquainted_count": "1",
    }
    assert rows[1]["status"] == "NOT_VISITED"
    assert "private note" not in csv_text


@pytest.mark.asyncio
async def test_couple_export_zip_contains_two_scoped_csv_files() -> None:
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")
    content = ContentItem(id=1, couple_id=1, title="Movie", category="MOVIE", added_by=100, status="COMPLETED")
    content.ratings = []
    content.comments = []
    foreign_content = ContentItem(id=2, couple_id=2, title="Other", category="MOVIE", added_by=100, status="COMPLETED")
    foreign_content.ratings = []
    foreign_content.comments = []
    place = PlaceItem(id=1, couple_id=1, title="Cafe", category="CAFE", added_by=100, status="VISITED")
    place.ratings = []
    place.comments = []

    service = CoupleExportService(
        content=FakeContentRepository([content, foreign_content]),
        places=FakePlaceRepository([place]),
    )

    couple_export = await service.build_export(
        couple,
        generated_at=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
    )

    assert couple_export.filename == "mately-export-20260526.zip"
    assert couple_export.content_type == "application/zip"
    assert couple_export.content_rows == 1
    assert couple_export.place_rows == 1

    with ZipFile(BytesIO(couple_export.data)) as archive:
        assert sorted(archive.namelist()) == ["content.csv", "places.csv"]
        content_csv = archive.read("content.csv").decode("utf-8")
        places_csv = archive.read("places.csv").decode("utf-8")

    assert content_csv.startswith(",".join(CONTENT_EXPORT_COLUMNS))
    assert places_csv.startswith(",".join(PLACES_EXPORT_COLUMNS))
    assert "Movie" in content_csv
    assert "Other" not in content_csv
    assert "Cafe" in places_csv
