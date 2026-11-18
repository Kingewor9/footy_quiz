from typing import List, Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator


class QuestionIn(BaseModel):
    type: Literal["poll", "text", "image"]
    text: str = Field(min_length=1, max_length=500)
    image_url: Optional[str] = None
    answer_mode: Literal["options", "text"] = "options"
    options: List[str] = []
    correct_index: Optional[int] = None
    accepted: List[str] = []
    points: int = Field(ge=1, le=1000)

    @model_validator(mode="after")
    def check(self):
        if self.type == "poll":
            self.answer_mode = "options"
        elif self.type == "text":
            self.answer_mode = "text"
        if self.type == "image":
            if not self.image_url or not self.image_url.lower().startswith(("http://", "https://")):
                raise ValueError("Image quiz needs a valid image link (http/https).")
        else:
            self.image_url = None
        if self.answer_mode == "options":
            self.options = [o.strip() for o in self.options]
            if not (2 <= len(self.options) <= 6) or any(not o for o in self.options):
                raise ValueError("Choose between 2 and 6 options and fill them all.")
            if self.correct_index is None or not (0 <= self.correct_index < len(self.options)):
                raise ValueError("Mark the correct option.")
            self.accepted = []
        else:
            self.accepted = [a.strip() for a in self.accepted if a.strip()]
            if not self.accepted:
                raise ValueError("Add at least one accepted answer.")
            self.options = []
            self.correct_index = None
        return self


class QuizIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    questions: List[QuestionIn] = Field(min_length=1, max_length=30)
    max_seconds: int = Field(default=60, ge=1, le=3600)
    status: Literal["live", "draft"] = "live"
    channel_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_quiz_settings(cls, values):
        if isinstance(values, dict):
            if "scheduled_at" in values:
                raise ValueError("Scheduled quizzes are no longer supported. Save the quiz as a draft instead.")
            if "expires_hours" in values or "expiration_hours" in values:
                raise ValueError("Quizzes close at the daily leaderboard reset; expiration is not configurable.")
        return values


class ImportQuizIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    questions: List[QuestionIn] = Field(min_length=1, max_length=30)
    max_seconds: int = Field(default=60, ge=1, le=3600)


class SubmitIn(BaseModel):
    answers: dict[str, str] = {}


class WinnerCardActionIn(BaseModel):
    day: str = Field(min_length=10, max_length=10)
    caption: Optional[str] = None
    channel_id: Optional[str] = None


class ChannelIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)


class BroadcastMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    image_url: Optional[str] = Field(default=None, max_length=2048)
    button_text: Optional[str] = Field(default=None, max_length=64)
    button_url: Optional[str] = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_message(self):
        self.text = self.text.strip()
        self.image_url = self.image_url.strip() if self.image_url and self.image_url.strip() else None
        self.button_text = self.button_text.strip() if self.button_text and self.button_text.strip() else None
        self.button_url = self.button_url.strip() if self.button_url and self.button_url.strip() else None

        if not self.text:
            raise ValueError("Enter a message to send.")
        if self.image_url and len(self.text) > 1024:
            raise ValueError("Messages with an image must be 1,024 characters or fewer.")
        if self.image_url and not is_http_url(self.image_url):
            raise ValueError("Enter a valid http or https image URL.")
        if bool(self.button_text) != bool(self.button_url):
            raise ValueError("Enter both a link URL and button text, or leave both blank.")
        if self.button_url and not is_http_url(self.button_url):
            raise ValueError("Enter a valid http or https button URL.")
        return self


def is_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        return False
