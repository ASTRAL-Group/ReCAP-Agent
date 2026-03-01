#!/usr/bin/env python3
"""Download and normalize datasets for dynamic_captchas.

This script prepares all datasets expected by the application:
1) Hugging Face text CAPTCHA dataset -> data/text_captcha
2) Kaggle reCAPTCHA category images -> data/recaptchav2/images/<Category>
3) Kaggle background images -> data/backgrounds
"""

from __future__ import annotations

import base64
import binascii
import json
import shutil
import sys
import os
import getpass
from pathlib import Path
from typing import Dict, Iterable

from PIL import Image, UnidentifiedImageError


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data"
DOWNLOAD_ROOT = DATA_ROOT / ".downloads"
TEXT_CAPTCHA_DIR = DATA_ROOT / "text_captcha"
RECAPTCHA_DIR = DATA_ROOT / "recaptchav2" / "images"
BACKGROUND_DIR = DATA_ROOT / "backgrounds"

HF_DATASET_ID = "yuxi5/captcha-data-clean"
KAGGLE_RECAPTCHA_DATASET = "mikhailma/test-dataset"
KAGGLE_BACKGROUND_DATASET = "nguyenquocdungk16hl/bg-20o"

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
EXPECTED_CATEGORIES = [
    "Traffic Light",
    "Crosswalk",
    "Bicycle",
    "Hydrant",
    "Car",
    "Bus",
    "Motorcycle",
    "Bridge",
    "Palm",
    "Stair",
    "Chimney",
    "Other",
]

# Normalized alias -> canonical category.
CATEGORY_ALIASES: Dict[str, str] = {
    "traffic light": "Traffic Light",
    "traffic lights": "Traffic Light",
    "crosswalk": "Crosswalk",
    "crosswalks": "Crosswalk",
    "bicycle": "Bicycle",
    "bicycles": "Bicycle",
    "hydrant": "Hydrant",
    "fire hydrant": "Hydrant",
    "fire hydrants": "Hydrant",
    "car": "Car",
    "cars": "Car",
    "bus": "Bus",
    "buses": "Bus",
    "motorcycle": "Motorcycle",
    "motorcycles": "Motorcycle",
    "bridge": "Bridge",
    "bridges": "Bridge",
    "palm": "Palm",
    "palm tree": "Palm",
    "palm trees": "Palm",
    "stair": "Stair",
    "stairs": "Stair",
    "chimney": "Chimney",
    "chimneys": "Chimney",
    "other": "Other",
}


def _parse_kaggle_api_token(raw_token: str) -> tuple[str, str]:
    token = raw_token.strip()
    if not token:
        raise RuntimeError("KAGGLE_API_TOKEN is set but empty.")

    # 1) JSON payload: {"username":"...","key":"..."}
    try:
        parsed = json.loads(token)
        if isinstance(parsed, dict):
            username = str(parsed.get("username", "")).strip()
            key = str(parsed.get("key", "")).strip()
            if username and key:
                return username, key
    except json.JSONDecodeError:
        pass

    # 2) Base64-encoded JSON payload.
    try:
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
        parsed = json.loads(decoded)
        if isinstance(parsed, dict):
            username = str(parsed.get("username", "")).strip()
            key = str(parsed.get("key", "")).strip()
            if username and key:
                return username, key
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        pass

    # 3) "username:key" fallback.
    if ":" in token:
        username, key = token.split(":", 1)
        username = username.strip()
        key = key.strip()
        if username and key:
            return username, key

    # 4) key-only token with KAGGLE_USERNAME provided separately.
    username = os.environ.get("KAGGLE_USERNAME", "").strip()
    if username:
        return username, token

    raise RuntimeError(
        "Unable to parse KAGGLE_API_TOKEN. Use one of: "
        "JSON {'username','key'}, base64(JSON), 'username:key', or set "
        "KAGGLE_USERNAME with key-only token."
    )


def _write_kaggle_config_files(username: str, key: str) -> None:
    payload = {"username": username, "key": key}
    content = json.dumps(payload, indent=2) + "\n"
    home = Path.home()

    config_dir = home / ".config" / "kaggle"
    legacy_dir = home / ".kaggle"
    config_dir.mkdir(parents=True, exist_ok=True)
    legacy_dir.mkdir(parents=True, exist_ok=True)
    config_dir.chmod(0o700)
    legacy_dir.chmod(0o700)

    config_file = config_dir / "kaggle.json"
    legacy_file = legacy_dir / "kaggle.json"
    config_file.write_text(content, encoding="utf-8")
    legacy_file.write_text(content, encoding="utf-8")
    config_file.chmod(0o600)
    legacy_file.chmod(0o600)

    os.environ["KAGGLE_USERNAME"] = username
    os.environ["KAGGLE_KEY"] = key
    os.environ.setdefault("KAGGLE_CONFIG_DIR", str(config_dir))


def _prompt_for_kaggle_api_token() -> str:
    if not sys.stdin.isatty():
        raise RuntimeError(
            "KAGGLE_API_TOKEN is not set. Export it first, e.g. "
            "export KAGGLE_API_TOKEN=KGAT_xxx"
        )
    token = getpass.getpass("Enter KAGGLE_API_TOKEN (KGAT_..., input hidden): ").strip()
    if not token:
        raise RuntimeError("KAGGLE_API_TOKEN input was empty.")
    return token


def _ensure_kaggle_api_token() -> str:
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if token:
        return token
    token = _prompt_for_kaggle_api_token()
    os.environ["KAGGLE_API_TOKEN"] = token
    print("[ok] Loaded KAGGLE_API_TOKEN from interactive input")
    return token


def _bootstrap_kaggle_auth_from_token_if_present() -> None:
    raw_token = _ensure_kaggle_api_token()

    # New standard token format (KGAT_...) should be passed through directly.
    if raw_token.startswith("KGAT_"):
        return

    # Backward-compatible fallback for older token styles.
    username, key = _parse_kaggle_api_token(raw_token)
    _write_kaggle_config_files(username, key)
    print("[ok] Converted legacy KAGGLE_API_TOKEN into Kaggle credentials")


def _normalize_token(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return " ".join(cleaned.split())


def _iter_images(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
            yield path


def _guess_category(path: Path) -> str:
    candidates = list(path.parts[-6:]) + [path.stem]
    for raw in reversed(candidates):
        token = _normalize_token(raw)
        if token in CATEGORY_ALIASES:
            return CATEGORY_ALIASES[token]

    # Broad substring fallback
    normalized = _normalize_token(str(path))
    for alias, canonical in CATEGORY_ALIASES.items():
        if alias in normalized:
            return canonical

    return "Other"


def _load_kaggle_api():
    _bootstrap_kaggle_auth_from_token_if_present()

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'kaggle'. Install it with: pip install kaggle"
        ) from exc

    # Kaggle CLI may expect ~/.config/kaggle/kaggle.json, while many setups use ~/.kaggle/kaggle.json.
    home = Path.home()
    raw_api_token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    kaggle_config_dir = os.environ.get("KAGGLE_CONFIG_DIR")
    default_config = home / ".config" / "kaggle" / "kaggle.json"
    legacy_config = home / ".kaggle" / "kaggle.json"
    has_env_creds = bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
    has_api_token = bool(raw_api_token)

    if not kaggle_config_dir and not default_config.exists() and legacy_config.exists():
        os.environ["KAGGLE_CONFIG_DIR"] = str(legacy_config.parent)

    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as exc:  # noqa: BLE001
        expected_dir = Path(os.environ.get("KAGGLE_CONFIG_DIR", str(home / ".config" / "kaggle")))
        token_hint = ""
        if raw_api_token.startswith("KGAT_"):
            token_hint = " KGAT token detected; if auth still fails, upgrade kaggle package."
        raise RuntimeError(
            "Kaggle authentication failed. Put kaggle.json in "
            f"'{expected_dir}' (or set KAGGLE_CONFIG_DIR), or export KAGGLE_USERNAME/KAGGLE_KEY, "
            "or provide KAGGLE_API_TOKEN. "
            f"Detected files: ~/.config/kaggle/kaggle.json={'yes' if default_config.exists() else 'no'}, "
            f"~/.kaggle/kaggle.json={'yes' if legacy_config.exists() else 'no'}, "
            f"env_credentials={'yes' if has_env_creds else 'no'}, "
            f"api_token={'yes' if has_api_token else 'no'}.{token_hint}"
        ) from exc
    return api


def download_text_captcha() -> None:
    if TEXT_CAPTCHA_DIR.exists():
        print(f"[skip] Text CAPTCHA dataset already exists: {TEXT_CAPTCHA_DIR}")
        return

    print(f"[download] Hugging Face dataset: {HF_DATASET_ID}")
    try:
        from datasets import load_from_disk
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'datasets' or 'huggingface_hub'. Install with: pip install -r requirements.txt"
        ) from exc

    TEXT_CAPTCHA_DIR.parent.mkdir(parents=True, exist_ok=True)
    temp_snapshot_dir = DOWNLOAD_ROOT / "hf_text_captcha_snapshot"
    if temp_snapshot_dir.exists():
        shutil.rmtree(temp_snapshot_dir)

    # Download the dataset repo as-is to avoid load_dataset() cache/fs incompatibilities.
    snapshot_download(
        repo_id=HF_DATASET_ID,
        repo_type="dataset",
        local_dir=str(temp_snapshot_dir),
        local_dir_use_symlinks=False,
    )

    # `yuxi5/captcha-data-clean` is uploaded as a datasets.save_to_disk directory.
    try:
        dataset = load_from_disk(str(temp_snapshot_dir))
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"{HF_DATASET_ID} is expected to be a save_to_disk dataset at repository root. "
            "Snapshot did not contain dataset artifacts (state.json + data-*.arrow)."
        ) from exc

    # Normalize to the runtime-expected schema: image + label.
    if "label" not in dataset.column_names:
        if "text" in dataset.column_names:
            dataset = dataset.rename_column("text", "label")
        elif "answer" in dataset.column_names:
            dataset = dataset.rename_column("answer", "label")
        elif "target" in dataset.column_names:
            dataset = dataset.rename_column("target", "label")
        else:
            raise RuntimeError(
                "Text dataset does not contain a recognized answer column. "
                f"Found columns: {dataset.column_names}"
            )

    dataset.save_to_disk(str(TEXT_CAPTCHA_DIR))
    print(f"[ok] Saved text dataset to: {TEXT_CAPTCHA_DIR}")


def _download_kaggle_dataset(dataset_ref: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    api = _load_kaggle_api()
    print(f"[download] Kaggle dataset: {dataset_ref}")
    api.dataset_download_files(dataset_ref, path=str(output_dir), unzip=True, quiet=False)
    print(f"[ok] Extracted to: {output_dir}")


def _save_png(src: Path, dst: Path) -> bool:
    try:
        with Image.open(src) as image:
            image.convert("RGB").save(dst, format="PNG")
    except (UnidentifiedImageError, OSError):
        return False
    return True


def _copy_background(src: Path, dst: Path) -> bool:
    try:
        if src.suffix.lower() == ".webp":
            with Image.open(src) as image:
                image.convert("RGB").save(dst.with_suffix(".jpg"), format="JPEG", quality=95)
        else:
            shutil.copy2(src, dst)
    except (UnidentifiedImageError, OSError, shutil.Error):
        return False
    return True


def prepare_recaptcha_images() -> None:
    if RECAPTCHA_DIR.exists() and any(RECAPTCHA_DIR.rglob("*.png")):
        print(f"[skip] ReCAPTCHA images already exist: {RECAPTCHA_DIR}")
        return

    source_dir = DOWNLOAD_ROOT / "kaggle_recaptcha"
    _download_kaggle_dataset(KAGGLE_RECAPTCHA_DATASET, source_dir)

    if RECAPTCHA_DIR.exists():
        shutil.rmtree(RECAPTCHA_DIR)
    RECAPTCHA_DIR.mkdir(parents=True, exist_ok=True)
    for category in EXPECTED_CATEGORIES:
        (RECAPTCHA_DIR / category).mkdir(parents=True, exist_ok=True)

    counters = {category: 0 for category in EXPECTED_CATEGORIES}
    copied = 0
    skipped = 0
    for src in _iter_images(source_dir):
        category = _guess_category(src)
        index = counters[category]
        dst = RECAPTCHA_DIR / category / f"{category.lower().replace(' ', '_')}_{index:06d}.png"
        if _save_png(src, dst):
            counters[category] += 1
            copied += 1
        else:
            skipped += 1

    print(f"[ok] ReCAPTCHA images prepared in: {RECAPTCHA_DIR}")
    print(f"     copied: {copied}, skipped: {skipped}")
    for category in EXPECTED_CATEGORIES:
        print(f"     {category}: {counters[category]}")


def prepare_backgrounds() -> None:
    if BACKGROUND_DIR.exists() and any(BACKGROUND_DIR.iterdir()):
        print(f"[skip] Background images already exist: {BACKGROUND_DIR}")
        return

    source_dir = DOWNLOAD_ROOT / "kaggle_backgrounds"
    _download_kaggle_dataset(KAGGLE_BACKGROUND_DATASET, source_dir)

    if BACKGROUND_DIR.exists():
        shutil.rmtree(BACKGROUND_DIR)
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    for idx, src in enumerate(_iter_images(source_dir)):
        ext = ".jpg" if src.suffix.lower() == ".webp" else src.suffix.lower()
        dst = BACKGROUND_DIR / f"bg_{idx:05d}{ext}"
        if _copy_background(src, dst):
            copied += 1
        else:
            skipped += 1

    print(f"[ok] Background images prepared in: {BACKGROUND_DIR}")
    print(f"     copied: {copied}, skipped: {skipped}")


def cleanup_download_cache() -> None:
    """Remove temporary download/extraction artifacts."""
    if not DOWNLOAD_ROOT.exists():
        return
    try:
        shutil.rmtree(DOWNLOAD_ROOT)
        print(f"[ok] Cleaned temporary downloads: {DOWNLOAD_ROOT}")
    except OSError as exc:
        print(f"[warn] Failed to clean temporary downloads ({DOWNLOAD_ROOT}): {exc}")


def main() -> int:
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    try:
        download_text_captcha()
        prepare_recaptcha_images()
        prepare_backgrounds()
        cleanup_download_cache()
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print("[done] Dataset preparation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
