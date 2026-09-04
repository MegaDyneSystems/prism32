"""Tests for announce-then-stop nudge detection (looks_like_announcement)."""
import prism32


def test_announcements_with_trailing_colon():
    assert prism32.looks_like_announcement(
        "Mini agent is up (PID 1522495, no errors). Now let me verify the complete final state and commit the bubble fix:")
    assert prism32.looks_like_announcement(
        "The blend 3D check failed on the served page. Let me verify the actual blend positions in the served HTML:")
    assert prism32.looks_like_announcement("Next steps:")


def test_announcements_with_intent_phrases():
    assert prism32.looks_like_announcement("Let me verify the layout checks.")
    assert prism32.looks_like_announcement("I'll examine both files to understand the harness.")
    assert prism32.looks_like_announcement("Now I will run the test suite.")
    assert prism32.looks_like_announcement("We'll check the served page next.")
    assert prism32.looks_like_announcement("Let me just check that quickly")
    assert prism32.looks_like_announcement("I am going to inspect the JSON file now.")


def test_final_answers_not_flagged():
    assert not prism32.looks_like_announcement("The task is complete. All checks pass.")
    assert not prism32.looks_like_announcement("Answer: 42")
    assert not prism32.looks_like_announcement("Let me know if you want anything else.")
    assert not prism32.looks_like_announcement("Here is a summary of what was changed.")
    assert not prism32.looks_like_announcement("")
    assert not prism32.looks_like_announcement(None)
