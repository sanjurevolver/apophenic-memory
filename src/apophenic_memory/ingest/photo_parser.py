from __future__ import annotations

from pathlib import Path

try:
    from exif import Image as ExifImage
except Exception:  # pragma: no cover - optional dependency for EXIF parsing
    ExifImage = None


def _read_exif_date(path: Path) -> str | None:
    """Return the EXIF original date in YYYY-MM-DD format, if available."""
    if ExifImage is None:
        return None

    try:
        with path.open('rb') as fh:
            image = ExifImage(fh)
        if not image.has_exif:
            return None
        if getattr(image, 'datetime_original', None):
            dt = image.datetime_original
            if isinstance(dt, str):
                return dt.split(' ')[0]
        if getattr(image, 'datetime_digitized', None):
            dt = image.datetime_digitized
            if isinstance(dt, str):
                return dt.split(' ')[0]
        if getattr(image, 'datetime', None):
            dt = image.datetime
            if isinstance(dt, str):
                return dt.split(' ')[0]
    except Exception:
        return None

    return None


def parse_photos(dir_path: Path) -> list[dict]:
    """Parse JPEG/PNG files in a directory and return their EXIF dates.

    Returns a list of dictionaries shaped like:
        {"date": "YYYY-MM-DD", "path": "..."}
    """
    if not isinstance(dir_path, Path):
        dir_path = Path(dir_path)

    if not dir_path.exists() or not dir_path.is_dir():
        return []

    entries: list[dict] = []
    for file_path in sorted(dir_path.iterdir()):
        if file_path.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
            continue

        date = _read_exif_date(file_path)
        if not date:
            continue

        entries.append({"date": date, "path": str(file_path)})

    return entries
