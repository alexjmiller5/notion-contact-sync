from notion_contact_sync import main


def test_run_dispatches_all_jobs_by_default(mocker):
    mocker.patch.dict(main.JOBS, {"enrich": lambda: {"a": 1}, "new_contacts": lambda: {"b": 2}})
    assert main.run() == {"enrich": {"a": 1}, "new_contacts": {"b": 2}}


def test_run_selects_named_job(mocker):
    enrich = mocker.Mock(return_value={})
    mocker.patch.dict(main.JOBS, {"enrich": enrich, "new_contacts": lambda: {"b": 2}})
    assert main.run(["new_contacts"]) == {"new_contacts": {"b": 2}}
    enrich.assert_not_called()
