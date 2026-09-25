from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = ROOT / "profile"
DB_PATH = ROOT / "data" / "jobagent.db"


class StyleRules(BaseModel):
    no_em_dash: bool = True
    no_en_dash: bool = True
    max_pages: int = 1
    filename_pattern: str = "Hillary_Mupfumi_{doc_type}_{company}_{tag}"


class Rules(BaseModel):
    target_titles: list[str] = []
    locations: dict = {}
    salary_floor_usd: int | None = None
    graduation_date_requirement: str | None = None
    sponsorship_required: bool = False
    resume_variants: list[dict] = []
    style: StyleRules = StyleRules()


@lru_cache
def load_rules() -> Rules:
    with open(PROFILE_DIR / "rules.yaml") as f:
        return Rules.model_validate(yaml.safe_load(f))


@lru_cache
def load_companies() -> list[dict]:
    with open(PROFILE_DIR / "companies.yaml") as f:
        data = yaml.safe_load(f) or {}
    return data.get("companies", [])


@lru_cache
def load_answers() -> dict:
    with open(PROFILE_DIR / "answers.yaml") as f:
        return yaml.safe_load(f) or {}
