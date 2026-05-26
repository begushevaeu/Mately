from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentItem, Couple, PlaceItem
from app.repositories.content import ContentRepository
from app.repositories.places import PlaceRepository
from app.services.content import average_rating as average_content_rating
from app.services.content import format_reactions
from app.services.places import average_rating as average_place_rating
from app.services.places import NOT_ACQUAINTED_RESPONSE
from app.utils.dates import get_timezone

CONTENT_EXPORT_COLUMNS = [
    "title",
    "category",
    "status",
    "completed_at",
    "average_rating",
    "reactions",
    "comments_count",
]
PLACES_EXPORT_COLUMNS = [
    "title",
    "category",
    "status",
    "visited_at",
    "average_rating",
    "comments_count",
    "not_acquainted_count",
]


@dataclass(frozen=True, slots=True)
class CoupleExport:
    filename: str
    content_type: str
    data: bytes
    content_rows: int
    place_rows: int


class CoupleExportService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        content: ContentRepository | None = None,
        places: PlaceRepository | None = None,
    ) -> None:
        if session is None and (content is None or places is None):
            raise ValueError("session is required when repositories are not provided")

        self.content = content or ContentRepository(session)  # type: ignore[arg-type]
        self.places = places or PlaceRepository(session)  # type: ignore[arg-type]

    async def build_export(
        self,
        couple: Couple,
        *,
        generated_at: datetime | None = None,
    ) -> CoupleExport:
        generated_at = generated_at or datetime.now(timezone.utc)
        content_items = await self.content.list_for_couple(couple.id)
        place_items = await self.places.list_for_couple(couple.id)
        timezone_name = couple.timezone or "Europe/Moscow"

        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("content.csv", build_content_csv(content_items, timezone_name))
            archive.writestr("places.csv", build_places_csv(place_items, timezone_name))

        filename = f"mately-export-{generated_at.astimezone(get_timezone(timezone_name)).strftime('%Y%m%d')}.zip"
        return CoupleExport(
            filename=filename,
            content_type="application/zip",
            data=zip_buffer.getvalue(),
            content_rows=len(content_items),
            place_rows=len(place_items),
        )


def build_content_csv(items: list[ContentItem], timezone_name: str) -> str:
    rows = [
        {
            "title": item.title,
            "category": item.category,
            "status": item.status,
            "completed_at": format_export_datetime(item.completed_at, timezone_name),
            "average_rating": format_export_rating(average_content_rating(item)),
            "reactions": format_reactions(item),
            "comments_count": str(len(item.comments)),
        }
        for item in items
    ]
    return build_csv(CONTENT_EXPORT_COLUMNS, rows)


def build_places_csv(items: list[PlaceItem], timezone_name: str) -> str:
    rows = [
        {
            "title": item.title,
            "category": item.category,
            "status": item.status,
            "visited_at": format_export_datetime(item.visited_at, timezone_name),
            "average_rating": format_export_rating(average_place_rating(item)),
            "comments_count": str(len(item.comments)),
            "not_acquainted_count": str(
                len([rating for rating in item.ratings if rating.response == NOT_ACQUAINTED_RESPONSE])
            ),
        }
        for item in items
    ]
    return build_csv(PLACES_EXPORT_COLUMNS, rows)


def build_csv(columns: list[str], rows: list[dict[str, str]]) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def format_export_datetime(value: datetime | None, timezone_name: str) -> str:
    if value is None:
        return ""
    return value.astimezone(get_timezone(timezone_name)).strftime("%Y-%m-%d %H:%M")


def format_export_rating(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.1f}"
