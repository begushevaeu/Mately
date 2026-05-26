from datetime import datetime, timezone

from app.analytics import (
    build_monthly_recap_text,
    build_recap_period,
    build_weekly_recap_text,
    collect_recap_stats,
)
from app.models import ContentItem, PlaceItem, PlaceRating, Rating, ShoppingItem, Task


def test_weekly_recap_counts_completed_tasks_content_ratings_and_overdue() -> None:
    local_now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    completed_task = Task(
        id=1,
        title="Полить цветы",
        created_by=1,
        assigned_to=2,
        status="COMPLETED",
        completed_at=datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc),
    )
    old_completed_task = Task(
        id=2,
        title="Старое дело",
        created_by=1,
        assigned_to=2,
        status="COMPLETED",
        completed_at=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc),
    )
    overdue_task = Task(
        id=3,
        title="Просрочка",
        created_by=1,
        assigned_to=2,
        status="ASSIGNED",
        deadline=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )
    completed_content = ContentItem(
        id=1,
        title="Фильм",
        category="MOVIE",
        added_by=1,
        status="COMPLETED",
        completed_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
    )
    completed_content.ratings = [
        Rating(content_id=1, user_id=1, score=9, emoji=None),
        Rating(content_id=1, user_id=2, score=7, emoji=None),
        Rating(content_id=1, user_id=3, score=None, emoji=None, response="NOT_ACQUAINTED"),
    ]
    old_content = ContentItem(
        id=2,
        title="Книга",
        category="BOOK",
        added_by=2,
        status="COMPLETED",
        completed_at=datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
    )
    old_content.ratings = [Rating(content_id=2, user_id=1, score=10, emoji=None)]

    stats = collect_recap_stats(
        [completed_task, old_completed_task, overdue_task],
        [completed_content, old_content],
        local_now=local_now,
        period="week",
    )

    assert stats.completed_tasks_count == 1
    assert stats.completed_content_count == 1
    assert stats.average_rating == 8
    assert stats.overdue_tasks_count == 1
    assert "Закрыто задач: 1" in build_weekly_recap_text(stats)
    assert "Средняя оценка: 8.0/10" in build_weekly_recap_text(stats)


def test_weekly_recap_counts_shopping_places_and_top_memory() -> None:
    local_now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    bought = ShoppingItem(
        id=1,
        title="Молоко",
        couple_id=1,
        added_by=1,
        status="BOUGHT",
        completed_at=datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc),
    )
    archived_bought = ShoppingItem(
        id=2,
        title="Хлеб",
        couple_id=1,
        added_by=1,
        status="ARCHIVED",
        completed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )
    old_bought = ShoppingItem(
        id=3,
        title="Старое",
        couple_id=1,
        added_by=1,
        status="ARCHIVED",
        completed_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
    )
    visited = PlaceItem(
        id=1,
        title="Sage <3",
        couple_id=1,
        category="RESTAURANT",
        added_by=1,
        status="VISITED",
        visited_at=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )
    visited.ratings = [
        PlaceRating(place_id=1, user_id=1, score=10, response="RATED"),
        PlaceRating(place_id=1, user_id=2, score=8, response="RATED"),
    ]
    old_visited = PlaceItem(
        id=2,
        title="Старый парк",
        couple_id=1,
        category="PARK",
        added_by=1,
        status="VISITED",
        visited_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
    )
    old_visited.ratings = [PlaceRating(place_id=2, user_id=1, score=1, response="RATED")]

    stats = collect_recap_stats(
        [],
        [],
        [bought, archived_bought, old_bought],
        [visited, old_visited],
        local_now=local_now,
        period="week",
    )
    text = build_weekly_recap_text(stats)

    assert stats.bought_shopping_count == 2
    assert stats.visited_places_count == 1
    assert stats.average_place_rating == 9
    assert stats.place_memory_title == "Sage <3"
    assert "Куплено из списка: 2" in text
    assert "Посещено мест: 1" in text
    assert "Средняя оценка мест: 9.0/10" in text
    assert "Место периода: Sage &lt;3, 9.0/10" in text


def test_monthly_period_on_first_day_uses_previous_month() -> None:
    period = build_recap_period(datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc), "month")

    assert period.label == "май"
    assert period.start == datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    assert period.end == datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)


def test_monthly_recap_contains_playful_title_and_cozy_summary() -> None:
    local_now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    tasks = [
        Task(
            id=index,
            title=f"Задача {index}",
            created_by=1,
            assigned_to=2,
            status="COMPLETED",
            completed_at=datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc),
        )
        for index in range(1, 17)
    ]
    stats = collect_recap_stats(tasks, [], local_now=local_now, period="month")
    text = build_monthly_recap_text(stats)

    assert "Ваш май: «Бытовой спецотряд мягкой силы»" in text
    assert "Закрыто задач: 16" in text
    assert "Котики" in text
