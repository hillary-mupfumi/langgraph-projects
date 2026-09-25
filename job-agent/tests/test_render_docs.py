import json

import pytest

from jobagent.nodes import render_docs

SAMPLE_PROFILE = {"name": "Jordan Rivera"}


@pytest.fixture
def profile_path(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(SAMPLE_PROFILE))
    return path


def test_run_renders_resume_and_cover_letter(tmp_path, profile_path):
    state = {
        "job": {"company_name": "Acme"},
        "resume_variant": "data-analytics",
        "tailored_resume": {"summary": "Summary", "bullets": [], "skills": []},
        "cover_letter": "Dear hiring team,",
    }

    result = render_docs.run(state, out_dir=tmp_path, profile_path=profile_path)

    assert result["resume_path"].endswith(".docx")
    assert result["cover_letter_path"].endswith(".docx")
    from pathlib import Path

    assert Path(result["resume_path"]).exists()
    assert Path(result["cover_letter_path"]).exists()
