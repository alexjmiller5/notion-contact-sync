import json

import pytest

from notion_contact_sync import new_contacts as nc


def make_person(pid: str, name: str) -> dict:
    return {
        "id": pid,
        "url": f"https://www.notion.so/{pid}",
        "properties": {"Name": {"title": [{"plain_text": name}]}},
    }


@pytest.fixture
def client(mocker):
    c = mocker.Mock()
    c.post.return_value = mocker.Mock(status_code=200)
    return c


def test_fetch_untagged_people_filters_empty_tags_and_paginates(client, mocker):
    client.post.side_effect = [
        mocker.Mock(
            json=lambda: {
                "results": [make_person("p1", "A")],
                "has_more": True,
                "next_cursor": "c1",
            }
        ),
        mocker.Mock(
            json=lambda: {
                "results": [make_person("p2", "B")],
                "has_more": False,
                "next_cursor": None,
            }
        ),
    ]
    people = nc.fetch_untagged_people(client)
    assert [p["id"] for p in people] == ["p1", "p2"]
    first_body = client.post.call_args_list[0].kwargs["json"]
    assert first_body["filter"] == {"property": nc.TAGS_PROP, "multi_select": {"is_empty": True}}
    assert first_body["sorts"] == [{"property": "Created time", "direction": "ascending"}]
    assert "start_cursor" not in first_body
    assert client.post.call_args_list[1].kwargs["json"]["start_cursor"] == "c1"


def test_task_payload_shape():
    payload = nc.task_payload(make_person("p1", "Jane Doe"))
    assert payload["parent"] == {"type": "data_source_id", "data_source_id": nc.TASKS_DS}
    props = payload["properties"]
    assert props["Name"]["title"][0]["text"]["content"] == "Tag & categorize contact: Jane Doe"
    assert props["Status"] == {"status": {"name": "To Do"}}
    assert props["Priority"] == {"select": {"name": "Low"}}
    assert props["Notes"]["rich_text"][0]["text"]["content"] == "https://www.notion.so/p1"
    assert props["Project"] == {"relation": [{"id": nc.PROJECT_PAGE_ID}]}


def test_run_creates_tasks_and_records_state(client, mocker, tmp_path, monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "t")
    state = tmp_path / "state.json"
    mocker.patch.object(nc, "fetch_untagged_people", return_value=[make_person("p1", "A")])
    mocker.patch.object(
        nc.httpx, "Client", return_value=mocker.MagicMock(__enter__=lambda s: client)
    )
    result = nc.run(max_tasks=30, state_path=state)
    assert result == {"created": 1, "skipped": 0, "remaining": 0}
    create_call = client.post.call_args_list[-1]
    assert create_call.args[0].endswith("/pages")
    assert json.loads(state.read_text()) == ["p1"]


def test_run_dedups_via_state_file(client, mocker, tmp_path, monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "t")
    state = tmp_path / "state.json"
    state.write_text('["p1"]')
    mocker.patch.object(nc, "fetch_untagged_people", return_value=[make_person("p1", "A")])
    mocker.patch.object(
        nc.httpx, "Client", return_value=mocker.MagicMock(__enter__=lambda s: client)
    )
    result = nc.run(max_tasks=30, state_path=state)
    assert result == {"created": 0, "skipped": 1, "remaining": 0}
    client.post.assert_not_called()


def test_run_caps_creations(client, mocker, tmp_path, monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "t")
    state = tmp_path / "state.json"
    people = [make_person(f"p{i}", f"P{i}") for i in range(5)]
    mocker.patch.object(nc, "fetch_untagged_people", return_value=people)
    mocker.patch.object(
        nc.httpx, "Client", return_value=mocker.MagicMock(__enter__=lambda s: client)
    )
    result = nc.run(max_tasks=2, state_path=state)
    assert result == {"created": 2, "skipped": 0, "remaining": 3}
    # only the created ones enter state, so a later run picks up the remainder
    assert json.loads(state.read_text()) == ["p0", "p1"]
