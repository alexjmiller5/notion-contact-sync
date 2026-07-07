"""Tests for enrich: per-source parsers + name matcher (fixtures anonymized)."""

import json

from notion_contact_sync.enrich import (
    build_people_index,
    match,
    normalize,
    parse_facebook,
    parse_instagram,
    parse_linkedin,
    parse_snapchat,
)

# --- fixtures (structure copied from real exports, names anonymized) ---

IG_ENTRY = {
    "title": "",
    "media_list_data": [],
    "string_list_data": [
        {"href": "https://www.instagram.com/jane.doe", "value": "jane.doe", "timestamp": 1}
    ],
}
IG_ENTRY2 = {
    "title": "",
    "media_list_data": [],
    "string_list_data": [
        {"href": "https://www.instagram.com/bobsmith99", "value": "bobsmith99", "timestamp": 2}
    ],
}


def person(pid, name, first="", last="", nick="", ig=None, fb=None, snap="", li=""):
    def rt(v):
        return [{"plain_text": v, "text": {"content": v}}] if v else []

    return {
        "id": pid,
        "url": f"https://notion.so/{pid}",
        "properties": {
            "Name": {"title": rt(name)},
            "First Name": {"rich_text": rt(first)},
            "Last Name": {"rich_text": rt(last)},
            "Nickname": {"rich_text": rt(nick)},
            "Instagram": {"url": ig},
            "Facebook": {"url": fb},
            "Snapchat": {"rich_text": rt(snap)},
            "LinkedIn URL": {"rich_text": rt(li)},
        },
    }


# --- normalize ---


def test_normalize():
    assert normalize("Jane Doe") == "janedoe"
    assert normalize("jane.doe_99") == "janedoe"  # punctuation + digits stripped
    assert normalize("José Álvarez") == "josealvarez"  # accents stripped
    assert normalize("O'Brien, Seán") == "obriensean"
    assert normalize("🔥Anthony Mitchell") == "anthonymitchell"
    assert normalize("") == ""


# --- parsers ---


def test_parse_instagram(tmp_path):
    followers = tmp_path / "followers.json"
    following = tmp_path / "following.json"
    followers.write_text(json.dumps([IG_ENTRY]))
    following.write_text(json.dumps({"relationships_following": [IG_ENTRY, IG_ENTRY2]}))
    recs = parse_instagram(followers, following)
    assert len(recs) == 2  # deduped by username
    jane = next(r for r in recs if r["username"] == "jane.doe")
    assert jane["source"] == "instagram"
    assert jane["profile_url"] == "https://www.instagram.com/jane.doe"


def test_parse_facebook(tmp_path):
    p = tmp_path / "your_friends.json"
    p.write_text(json.dumps({"friends_v2": [{"name": "Jane Doe", "timestamp": 1}]}))
    recs = parse_facebook(p)
    assert recs == [
        {"source": "facebook", "username": "", "display_name": "Jane Doe", "profile_url": ""}
    ]


def test_parse_snapchat(tmp_path):
    p = tmp_path / "friends.json"
    p.write_text(
        json.dumps(
            {
                "Friends": [
                    {
                        "Username": "jdoe123",
                        "Display Name": "Jane Doe",
                        "Creation Timestamp": "2016-05-12 00:33:26 UTC",
                        "Last Modified Timestamp": "2016-05-12 00:33:26 UTC",
                        "Source": "added by phone",
                    }
                ],
                "Blocked Users": [{"Username": "ignored", "Display Name": "Ignored"}],
            }
        )
    )
    recs = parse_snapchat(p)
    assert recs == [
        {"source": "snapchat", "username": "jdoe123", "display_name": "Jane Doe", "profile_url": ""}
    ]


def test_parse_linkedin(tmp_path):
    p = tmp_path / "Connections.csv"
    # Real file starts with a Notes preamble before the header row.
    p.write_text(
        "Notes:\n"
        '"When exporting your connection data, you may notice..."\n'
        "\n"
        "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
        "Jane,Doe,https://www.linkedin.com/in/janedoe,,Acme,Engineer,30 May 2025\n"
    )
    recs = parse_linkedin(p)
    assert recs == [
        {
            "source": "linkedin",
            "username": "",
            "display_name": "Jane Doe",
            "profile_url": "https://www.linkedin.com/in/janedoe",
        }
    ]


# --- matcher ---


def li_rec(name="Jane Doe", url="https://www.linkedin.com/in/janedoe"):
    return {"source": "linkedin", "username": "", "display_name": name, "profile_url": url}


def test_match_exact_hit():
    people = [person("p1", "Jane Doe")]
    applies, review = match([li_rec()], build_people_index(people))
    assert len(applies) == 1
    a = applies[0]
    assert (a["person_id"], a["prop"], a["value"]) == (
        "p1",
        "LinkedIn URL",
        "https://www.linkedin.com/in/janedoe",
    )
    assert review == []


def test_match_instagram_username_vs_full_name():
    people = [person("p1", "Jane Doe")]
    rec = {
        "source": "instagram",
        "username": "jane.doe_99",
        "display_name": "",
        "profile_url": "https://www.instagram.com/jane.doe_99",
    }
    applies, _ = match([rec], build_people_index(people))
    assert len(applies) == 1
    assert applies[0]["prop"] == "Instagram"
    assert applies[0]["value"] == "https://www.instagram.com/jane.doe_99"


def test_match_no_hit_goes_to_review():
    applies, review = match(
        [li_rec("Stranger Person")], build_people_index([person("p1", "Jane Doe")])
    )
    assert applies == []
    assert len(review) == 1
    assert review[0]["status"] == "unmatched"


def test_match_ambiguous_multiple_people():
    people = [person("p1", "Jane Doe"), person("p2", "", first="Jane", last="Doe")]
    applies, review = match([li_rec()], build_people_index(people))
    assert applies == []
    assert review[0]["status"] == "ambiguous_person"
    assert "p1" in review[0]["candidates"] and "p2" in review[0]["candidates"]


def test_match_ambiguous_multiple_records_same_name():
    recs = [
        li_rec(url="https://www.linkedin.com/in/janedoe"),
        li_rec(url="https://www.linkedin.com/in/janedoe2"),
    ]
    applies, review = match(recs, build_people_index([person("p1", "Jane Doe")]))
    assert applies == []
    assert {r["status"] for r in review} == {"ambiguous_record"}
    assert len(review) == 2


def test_match_skips_nonempty_property():
    people = [person("p1", "Jane Doe", li="https://www.linkedin.com/in/existing")]
    applies, review = match([li_rec()], build_people_index(people))
    assert applies == []
    assert review == []  # already-filled is a silent skip, not a review item


def test_match_facebook_no_url_goes_to_review():
    rec = {"source": "facebook", "username": "", "display_name": "Jane Doe", "profile_url": ""}
    applies, review = match([rec], build_people_index([person("p1", "Jane Doe")]))
    assert applies == []  # FB export has no profile URLs; nothing to write to a url prop
    assert review[0]["status"] == "matched_no_url"


def test_match_single_word_person_name_goes_to_review():
    rec = {
        "source": "instagram",
        "username": "alexa.2472",
        "display_name": "",
        "profile_url": "https://www.instagram.com/alexa.2472",
    }
    applies, review = match([rec], build_people_index([person("p1", "Alexa")]))
    assert applies == []
    assert review[0]["status"] == "single_name_match"


def test_match_nickname_key():
    people = [person("p1", "Jonathan Doe", nick="Jonny", last="Doe")]
    applies, _ = match([li_rec("Jonny Doe")], build_people_index(people))
    assert len(applies) == 1
