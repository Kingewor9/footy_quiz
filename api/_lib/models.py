from typing import List, Literal, Optional

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

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_quiz_settings(cls, values):
        if isinstance(values, dict):
            if "scheduled_at" in values:
                raise ValueError("Scheduled quizzes are no longer supported. Save the quiz as a draft instead.")
            if "expires_hours" in values or "expiration_hours" in values:
                raise ValueError("Quizzes close at the daily leaderboard reset; expiration is not configurable.")
        return values


class SubmitIn(BaseModel):
    answers: dict[str, str] = {}


class WinnerCardActionIn(BaseModel):
    day: str = Field(min_length=10, max_length=10)
    caption: Optional[str] = None
