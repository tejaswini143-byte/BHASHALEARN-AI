import sys
from types import SimpleNamespace

import pytest

from pocs.poc06_bilingual_voice.audio import AudioInputError, MicrophoneRecorder, WavAudioInput
from pocs.poc06_bilingual_voice.tests.helpers import sample_wav


def write_wav(path, data=None):
    path.write_bytes(data if data is not None else sample_wav())
    return path


def test_valid_wav_uses_poc01_constraints(tmp_path):
    capture = WavAudioInput.from_file(write_wav(tmp_path / "valid.wav"))
    assert capture.path.is_file()
    assert capture.temporary is False


def test_invalid_audio_format_is_rejected(tmp_path):
    path = tmp_path / "recording.mp3"
    path.write_bytes(b"audio")
    with pytest.raises(AudioInputError, match="PCM .wav"):
        WavAudioInput.from_file(path)


def test_missing_audio_file_is_rejected(tmp_path):
    with pytest.raises(AudioInputError, match="does not exist"):
        WavAudioInput.from_file(tmp_path / "missing.wav")


def test_empty_pcm_wav_is_rejected(tmp_path):
    with pytest.raises(AudioInputError, match="empty"):
        WavAudioInput.from_file(write_wav(tmp_path / "empty.wav", sample_wav(frames=0)))


def test_microphone_capture_is_optional_and_temp_is_cleaned(monkeypatch):
    class Samples:
        def __init__(self, data):
            self.data = data

        def tobytes(self):
            return self.data

    fake_device = SimpleNamespace(
        rec=lambda frames, samplerate, channels, dtype: Samples(b"\x00\x00" * frames * channels),
        wait=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_device)
    capture = MicrophoneRecorder(sample_rate=16000, channels=1).record(0.01)
    assert capture.path.is_file()
    assert capture.temporary
    path = capture.path
    capture.cleanup()
    assert not path.exists()


def test_microphone_duration_is_bounded():
    recorder = MicrophoneRecorder(max_seconds=3)
    with pytest.raises(AudioInputError, match="between 0 and 3"):
        recorder.record(4)

