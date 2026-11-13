from pathlib import Path
import tomllib

from .models import GateError

ITEMS = ("readme", "changelog", "license", "junit")


def load_config(project: Path) -> dict[str, str]:
    try:
        with (project / "release-gate.toml").open("rb") as stream:
            config = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise GateError("config_missing", "release-gate.toml não encontrado.") from exc
    except (tomllib.TOMLDecodeError, UnicodeError) as exc:
        raise GateError("config_invalid", "release-gate.toml contém TOML inválido.") from exc
    except OSError as exc:
        raise GateError("config_read_error", "Não foi possível ler release-gate.toml.") from exc

    if (
        set(config) != {"schema_version", "checklist"}
        or type(config.get("schema_version")) is not int
        or config["schema_version"] != 1
        or not isinstance(config.get("checklist"), dict)
        or set(config["checklist"]) != set(ITEMS)
        or any(not isinstance(path, str) or not path.strip()
               for path in config["checklist"].values())
    ):
        raise GateError("config_invalid", "Configuração inválida: use schema_version = 1 e checklist com readme, changelog, license e junit como caminhos não vazios.")
    return {item: config["checklist"][item] for item in ITEMS}


def resolve_item(project: Path, configured_path: str, item: str) -> Path:
    path = Path(configured_path)
    code = f"{item}_path_invalid"
    if path.is_absolute():
        raise GateError(code, f"{item}: o caminho deve ser relativo à pasta do projeto.")
    try:
        root = project.resolve(strict=True)
        resolved = (root / path).resolve()
        if "\0" in configured_path:
            raise ValueError("NUL in path")
    except (OSError, RuntimeError, ValueError) as exc:
        raise GateError(code, f"{item}: não foi possível resolver o caminho.") from exc
    if not resolved.is_relative_to(root):
        raise GateError(code, f"{item}: o caminho sai da pasta do projeto.")
    return resolved
