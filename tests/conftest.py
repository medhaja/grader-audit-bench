import pytest

from audit.generate import load_cases, load_tasks


@pytest.fixture(scope="session")
def tasks():
    return {t["id"]: t for t in load_tasks()}


@pytest.fixture(scope="session")
def cases():
    return load_cases()


@pytest.fixture(scope="session")
def audit_results():
    from audit.runner import run_audit
    from audit.graders.judge import MockJudge

    return run_audit(k=5, judge=MockJudge())
