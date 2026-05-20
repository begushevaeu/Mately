from __future__ import annotations

import random
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class CatNotificationType(StrEnum):
    COMPLETED = "completed"
    OVERDUE = "overdue"
    RECAP = "recap"
    SLEEPY = "sleepy"


class CatMood(StrEnum):
    HAPPY = "happy"
    SAD = "sad"
    SLEEPY = "sleepy"
    CELEBRATION = "celebration"


class RandomChoice(Protocol):
    def choice(self, sequence: list[Path]) -> Path:
        pass


CAT_ASSET_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_CAT_ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets" / "cats"

CAT_MOOD_BY_NOTIFICATION_TYPE = {
    CatNotificationType.COMPLETED: CatMood.HAPPY,
    CatNotificationType.OVERDUE: CatMood.SAD,
    CatNotificationType.RECAP: CatMood.CELEBRATION,
    CatNotificationType.SLEEPY: CatMood.SLEEPY,
}


def cat_mood_for_notification(notification_type: CatNotificationType | None) -> CatMood | None:
    if notification_type is None:
        return None

    return CAT_MOOD_BY_NOTIFICATION_TYPE.get(notification_type)


def list_cat_assets(mood: CatMood, *, root: Path | None = None) -> list[Path]:
    mood_folder = (root or DEFAULT_CAT_ASSETS_ROOT) / mood.value
    if not mood_folder.exists() or not mood_folder.is_dir():
        return []

    return sorted(
        path
        for path in mood_folder.iterdir()
        if path.is_file() and path.suffix.lower() in CAT_ASSET_EXTENSIONS
    )


def select_cat_asset(
    notification_type: CatNotificationType | None,
    *,
    root: Path | None = None,
    rng: RandomChoice | None = None,
) -> Path | None:
    mood = cat_mood_for_notification(notification_type)
    if mood is None:
        return None

    assets = list_cat_assets(mood, root=root)
    if not assets:
        return None

    return (rng or random.SystemRandom()).choice(assets)
