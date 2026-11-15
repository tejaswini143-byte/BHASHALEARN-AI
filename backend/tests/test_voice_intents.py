from app.voice import response_for

def test_acknowledgment_intent():
    assert response_for("Okay, I will submit it.", "en-IN", "Math homework")[0] == "acknowledged"

def test_snooze_intent():
    assert response_for("Remind me again in 30 minutes", "en-IN", "Math homework")[0] == "snooze"

def test_completed_intent():
    assert response_for("I have already completed it", "en-IN", "Math homework")[0] == "completed"

