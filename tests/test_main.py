from notion_contact_sync.main import run


def test_run_succeeds():
    assert run()["ok"] is True
