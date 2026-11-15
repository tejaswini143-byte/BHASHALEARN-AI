import asyncio
import io
import wave

from livekit import rtc
from livekit.agents import APIConnectOptions

from app.livekit_adapters import GnaniPrismaSTT, GnaniTimbreChunkedStream, GnaniTimbreTTS
from pocs.poc01_prisma_stt.prisma_stt import Transcript


class FakePrisma:
    def __init__(self):
        self.received = None

    def transcribe(self, path):
        with wave.open(str(path), "rb") as audio:
            self.received = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes())
        return Transcript("సరే, నేను సమర్పిస్తాను.", "te-IN", {})


class FakeTimbre:
    def synthesize(self, text, language, voice):
        assert language == "te-IN"
        assert voice == "Suhana"
        out = io.BytesIO()
        with wave.open(out, "wb") as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
            audio.writeframes(b"\x00\x00" * 4096)
        return out.getvalue()


def test_prisma_livekit_wrapper_sends_one_turn_wav_to_rest_adapter():
    adapter = GnaniPrismaSTT()
    fake = FakePrisma(); adapter._adapter = fake
    pcm = b"\x00\x00" * 8000
    frame = rtc.AudioFrame(data=pcm, sample_rate=16000, num_channels=1, samples_per_channel=8000)
    event = asyncio.run(adapter._recognize_impl(frame, language="te-IN", conn_options=APIConnectOptions()))
    assert adapter.capabilities.streaming is False
    assert fake.received == (1, 2, 16000, 8000)
    assert event.alternatives[0].text == "సరే, నేను సమర్పిస్తాను."


def test_timbre_livekit_wrapper_emits_wav_frames_without_claiming_streaming():
    adapter = GnaniTimbreTTS(language="te-IN")
    adapter._adapter = FakeTimbre()
    async def collect():
        frames = []
        async with adapter.synthesize("సరే.", conn_options=APIConnectOptions()) as stream:
            async for chunk in stream:
                frames.append(chunk.frame)
        return frames
    frames = asyncio.run(collect())
    assert adapter.capabilities.streaming is False
    assert frames
    assert frames[0].sample_rate == 48000
    assert frames[0].num_channels == 1
