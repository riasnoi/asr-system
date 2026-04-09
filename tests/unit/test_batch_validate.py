from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
VALIDATE_PATH = ROOT_DIR / "services" / "batch" / "validate.py"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_validate_module():
    spec = importlib.util.spec_from_file_location("test_batch_validate_module", VALIDATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_returns_skip_code_when_no_local_recordings(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from asr_system.config import get_settings

    validate = _load_validate_module()
    target_date = "2026-04-09"
    monkeypatch.setenv("BATCH_S3_BUCKET", "")
    monkeypatch.setenv("BATCH_INPUT_DIR", str(tmp_path))
    monkeypatch.setenv("AIRFLOW_CTX_LOGICAL_DATE", f"{target_date}T00:00:00+00:00")
    get_settings.cache_clear()

    exit_code = validate.main()

    assert exit_code == validate.NO_RECORDINGS_EXIT_CODE
    assert capsys.readouterr().out.strip() == f"validate [local]: 0 recordings for {target_date}"


def test_validate_returns_success_when_local_recordings_exist(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from asr_system.config import get_settings

    validate = _load_validate_module()
    target_date = "2026-04-09"
    input_dir = tmp_path / target_date
    input_dir.mkdir(parents=True)
    (input_dir / "call-001.wav").write_bytes(b"audio")
    (input_dir / "notes.txt").write_text("ignore")
    monkeypatch.setenv("BATCH_S3_BUCKET", "")
    monkeypatch.setenv("BATCH_INPUT_DIR", str(tmp_path))
    monkeypatch.setenv("AIRFLOW_CTX_LOGICAL_DATE", f"{target_date}T00:00:00+00:00")
    get_settings.cache_clear()

    exit_code = validate.main()

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == f"validate [local]: 1 recordings for {target_date}"


def test_validate_prefers_explicit_batch_target_date(monkeypatch, tmp_path: Path, capsys) -> None:
    from asr_system.config import get_settings

    validate = _load_validate_module()
    explicit_target_date = "2026-04-07"
    logical_date = "2026-04-09"
    input_dir = tmp_path / explicit_target_date
    input_dir.mkdir(parents=True)
    (input_dir / "call-001.wav").write_bytes(b"audio")
    monkeypatch.setenv("BATCH_S3_BUCKET", "")
    monkeypatch.setenv("BATCH_INPUT_DIR", str(tmp_path))
    monkeypatch.setenv("BATCH_TARGET_DATE", explicit_target_date)
    monkeypatch.setenv("AIRFLOW_CTX_LOGICAL_DATE", f"{logical_date}T00:00:00+00:00")
    get_settings.cache_clear()

    exit_code = validate.main()

    assert exit_code == 0
    assert (
        capsys.readouterr().out.strip()
        == f"validate [local]: 1 recordings for {explicit_target_date}"
    )
