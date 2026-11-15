from app.voice import response_for

def test_acknowledgment_intent():
    assert response_for("Okay, I will submit it.", "en-IN", "Math homework")[0] == "acknowledged"

def test_snooze_intent():
    assert response_for("Remind me again in 30 minutes", "en-IN", "Math homework")[0] == "snooze"

def test_completed_intent():
    assert response_for("I have already completed it", "en-IN", "Math homework")[0] == "completed"

def test_telugu_acknowledgment_and_response():
    intent, reply, _ = response_for("సరే, నేను సమర్పిస్తాను", "te-IN", "గణితం")
    assert intent == "acknowledged"
    assert "సరే" in reply

def test_telugu_snooze_and_tomorrow_intents():
    assert response_for("ముప్పై నిమిషాల తర్వాత గుర్తు చేయి", "te-IN", "గణితం")[0] == "snooze"
    assert response_for("రేపు గుర్తు చేయి", "te-IN", "గణితం")[0] == "reschedule"

def test_telugu_explicit_completion_intent():
    assert response_for("నేను ఇప్పటికే పూర్తి చేశాను", "te-IN", "గణితం")[0] == "completed"

