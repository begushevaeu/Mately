from datetime import datetime, timezone

from app.analytics import (
    build_monthly_recap_text,
    build_recap_period,
    build_weekly_recap_text,
    collect_recap_stats,
)
from app.models import ContentItem, Rating, Task


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
