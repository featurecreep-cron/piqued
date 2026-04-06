"""Pydantic schemas for the v1 JSON API."""

from datetime import datetime

from pydantic import BaseModel


# --- Sections (triage view) ---


class SectionItem(BaseModel):
    id: int
    article_id: int
    article_title: str
    feed_title: str
    heading: str | None
    summary: str
    topic_tags: list[str]
    score: float
    reasoning: str | None
    is_surprise: bool
    has_humor: bool
    has_surprise_data: bool
    has_actionable_advice: bool
    article_url: str | None
    published_at: datetime | None


class SectionList(BaseModel):
    sections: list[SectionItem]
    date: str
    dates_available: list[str]
    threshold: float
    surprise_section_ids: list[int]


# --- Feeds ---


class FeedItem(BaseModel):
    id: int
    title: str
    url: str | None
    category: str
    active: bool
    content_quality: str
    article_count: int


class FeedList(BaseModel):
    feeds: list[FeedItem]
    categories: dict[str, list[int]]


class ArticleSummary(BaseModel):
    id: int
    title: str
    url: str | None
    published_at: datetime | None
    status: str
    section_count: int


class FeedDetail(BaseModel):
    feed: FeedItem
    articles: list[ArticleSummary]


# --- Articles ---


class ArticleSection(BaseModel):
    id: int
    heading: str | None
    summary: str
    topic_tags: list[str]
    score: float
    reasoning: str | None
    is_surprise: bool
    has_humor: bool
    has_surprise_data: bool
    has_actionable_advice: bool


class ArticleDetail(BaseModel):
    id: int
    title: str
    url: str | None
    feed_title: str
    published_at: datetime | None
    status: str
    sections: list[ArticleSection]


# --- Profile ---


class WeightItem(BaseModel):
    topic: str
    weight: float
    feedback_count: int
    updated_at: datetime | None


class UserProfileResponse(BaseModel):
    profile_text: str
    profile_version: int
    pending_feedback_count: int
    last_synthesized_at: datetime | None
    weights: list[WeightItem]


class ProfileEditRequest(BaseModel):
    profile_text: str


# --- Users ---


class UserInfo(BaseModel):
    id: int
    username: str
    email: str | None
    role: str


class UserList(BaseModel):
    users: list[UserInfo]


# --- Settings ---


class SettingsResponse(BaseModel):
    settings: dict[str, str]
    is_admin: bool


class ConnectionTestResult(BaseModel):
    ok: bool
    detail: str


# --- Processing log ---


class ProcessingLogEntry(BaseModel):
    id: int
    article_id: int | None
    article_title: str | None
    stage: str
    status: str
    detail: str | None
    tokens_used: int | None
    duration_ms: int | None
    created_at: datetime


class ProcessingLogList(BaseModel):
    entries: list[ProcessingLogEntry]
    limit: int
    offset: int
    total: int


# --- Feedback ---


class FeedbackRequest(BaseModel):
    section_id: int
    rating: int
    reason: str | None = None


class FeedbackResult(BaseModel):
    ok: bool
    direction: str


# --- Feed sync ---


class SyncResult(BaseModel):
    ok: bool
    total: int
    added: int


# --- API keys ---


class ClickThroughRequest(BaseModel):
    section_id: int


class DownweightRequest(BaseModel):
    tag: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class ChangeRoleRequest(BaseModel):
    role: str


class ApiKeyCreate(BaseModel):
    name: str = ""


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    key: str


class ApiKeyItem(BaseModel):
    id: int
    name: str
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyList(BaseModel):
    keys: list[ApiKeyItem]


# --- User preferences ---


class UserPreferences(BaseModel):
    theme: str = "light"
    layout_mode: str = "river"
    items_per_page: int = 50
    column_config: list[str] | None = None


class UserPreferencesUpdate(BaseModel):
    theme: str | None = None
    layout_mode: str | None = None
    items_per_page: int | None = None
    column_config: list[str] | None = None
