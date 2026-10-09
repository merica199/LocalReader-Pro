from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


class LibraryItem(BaseModel):
    id: str
    fileName: str
    totalPages: int
    currentPage: int
    lastSentenceIndex: int
    lastAccessed: float


class ContentItem(BaseModel):
    id: str
    pages: List[str]


class PronunciationRule(BaseModel):
    id: str
    original: str
    replacement: str
    match_case: bool
    word_boundary: bool
    is_regex: Optional[bool] = False


class AppSettings(BaseModel):
    pronunciationRules: List[PronunciationRule]
    ignoreList: List[str]
    voice_id: Optional[str] = "af_bella"
    speed: Optional[float] = 1.0
    font_size: Optional[int] = 16
    header_footer_mode: Optional[str] = "off"
    engine_mode: Optional[str] = "gpu"
    ui_language: Optional[str] = "en"
    pause_settings: Optional[Dict[str, int]] = {
        "comma": 300,
        "period": 600,
        "question": 600,
        "exclamation": 600,
        "colon": 400,
        "semicolon": 400,
        "newline": 800,
        "paragraph": 1200,
    }


class TimerRequest(BaseModel):
    minutes: int


class ExportRequest(BaseModel):
    doc_id: str
    voice: str = "af_bella"
    speed: float = 1.0
    rules: List[PronunciationRule]
    ignore_list: List[str] = []


# Defaults here repeat Pacing in logic/sleep_script.py and Sound in
# logic/sleep_finish.py; a test checks they agree.
class SleepPacing(BaseModel):
    """Pause lengths, in seconds."""

    sentence: float = Field(1.0, ge=0, le=60)
    paragraph: float = Field(2.6, ge=0, le=60)
    ellipsis: float = Field(1.1, ge=0, le=60)
    clause: float = Field(0.3, ge=0, le=10)
    lead_in: float = Field(3.0, ge=0, le=600)
    # Up to an hour, for background sound that carries on after the voice.
    tail: float = Field(8.0, ge=0, le=3600)


class SleepSound(BaseModel):
    soften: Literal["off", "light", "medium", "strong"] = "light"
    room: Literal["off", "subtle", "roomy"] = "subtle"
    # LUFS; None leaves the voice at the level it was rendered at.
    loudness: Optional[float] = Field(-22.0, ge=-40, le=-10)
    # "none", "brown", "pink", "white", or "file:<name>" for an added sound.
    background: str = "brown"
    background_level: float = Field(-18.0, ge=-50, le=0)
    fade_in: float = Field(3.0, ge=0, le=600)
    fade_out: float = Field(45.0, ge=0, le=1800)
    format: Literal["mp3", "m4a", "wav"] = "mp3"
    bitrate: Literal[64, 96, 128, 192] = 96


class SleepSettings(BaseModel):
    # Slower than reading pace by default: the speed a sleep recording wants is
    # not the speed someone reads a book at.
    speed: float = Field(0.9, ge=0.5, le=1.5)
    pacing: SleepPacing = SleepPacing()
    sound: SleepSound = SleepSound()


class SleepExportRequest(SleepSettings, ExportRequest):
    # SleepSettings first, so its speed (0.9, bounded) wins over the reading speed.
    pass


class SynthesisRequest(BaseModel):
    text: str
    voice: str = "af_sky"
    speed: float = 1.0
    rules: List[PronunciationRule]
    ignore_list: List[str] = []
    pause_settings: Optional[Dict[str, int]] = {
        "comma": 300,
        "period": 600,
        "question": 600,
        "exclamation": 600,
        "colon": 400,
        "semicolon": 400,
        "newline": 800,
    }
