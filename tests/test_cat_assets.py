from __future__ import annotations

from pathlib import Path

from app.notifications.cats import (
    CatMood,
    CatNotificationType,
    cat_mood_for_notification,
    list_cat_assets,
    select_cat_asset,
)


class FirstChoice:
    def choice(self, sequence: list[Path]) -> Path:
        return sequence[0]


def test_cat_notification_types_map_to_moods() -> None:
    assert cat_mood_for_notification(CatNotificationType.COMPLETED) is CatMood.HAPPY
    assert cat_mood_for_notification(CatNotificationType.OVERDUE) is CatMood.SAD
    assert cat_mood_for_notification(CatNotificationType.RECAP) is CatMood.CELEBRATION
    assert cat_mood_for_notification(None) is None


def test_cat_asset_selection_uses_expected_folder_and_ignores_placeholders(tmp_path: Path) -> None:
    root = tmp_path / "cats"
    happy = root / "happy"
    happy.mkdir(parents=True)
    (happy / ".gitkeep").write_text("placeholder", encoding="utf-8")
    (happy / "z-cat.gif").write_text("ignored", encoding="utf-8")
    first = happy / "a-cat.png"
    second = happy / "b-cat.jpg"
    first.write_bytes(b"png")
    second.write_bytes(b"jpg")

    assert list_cat_assets(CatMood.HAPPY, root=root) == [first, second]
    assert select_cat_asset(CatNotificationType.COMPLETED, root=root, rng=FirstChoice()) == first


def test_missing_cat_assets_return_none(tmp_path: Path) -> None:
    assert select_cat_asset(CatNotificationType.OVERDUE, root=tmp_path) is None
