from dataclasses import asdict, dataclass, field


class GateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Result:
    status: str
    checks: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    schema_version: int = field(default=1, init=False)

    @property
    def exit_code(self) -> int:
        return {"passed": 0, "failed": 1, "error": 2}[self.status]

    def to_dict(self) -> dict:
        return asdict(self)
