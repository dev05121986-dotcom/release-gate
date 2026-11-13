from pathlib import Path
import stat

from .config import load_config, resolve_item
from .models import GateError, Result


def check_item(project: Path, item: str, configured_path: str) -> dict[str, str]:
    # Resolve and validate containment before inspecting the target or reading it.
    path = resolve_item(project, configured_path, item)
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        code, message = f"{item}_missing", f"{configured_path} não encontrado."
    except (OSError, ValueError) as exc:
        raise GateError(f"{item}_read_error", f"Não foi possível inspecionar {configured_path}.") from exc
    else:
        if not stat.S_ISREG(mode):
            if item == "changelog":
                raise GateError("changelog_read_error", f"{configured_path} não é um arquivo regular.")
            code, message = f"{item}_not_regular", f"{configured_path} não é um arquivo regular."
        elif item == "changelog":
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError, ValueError) as exc:
                raise GateError("changelog_read_error", f"Não foi possível ler {configured_path} como arquivo UTF-8.") from exc
            if content.strip():
                code, message = "changelog_valid", f"{configured_path} existe e contém texto."
            else:
                code, message = "changelog_empty", f"{configured_path} está vazio."
        else:
            code, message = f"{item}_valid", f"{configured_path} é um arquivo regular."
    return {
        "id": item, "status": "passed" if code == f"{item}_valid" else "failed",
        "code": code, "path": configured_path, "message": message,
    }


def check(project: Path) -> Result:
    try:
        checklist = load_config(project)
    except GateError as exc:
        return Result("error", errors=[{"code": exc.code, "message": str(exc)}])
    checks, errors = [], []
    for item, configured_path in checklist.items():
        try:
            checks.append(check_item(project, item, configured_path))
        except GateError as exc:
            entry = {"id": item, "status": "error", "code": exc.code,
                     "path": configured_path, "message": str(exc)}
            checks.append(entry)
            errors.append({key: entry[key] for key in ("id", "path", "code", "message")})
    status = "error" if errors else (
        "failed" if any(entry["status"] == "failed" for entry in checks) else "passed"
    )
    return Result(status, checks=checks, errors=errors)
