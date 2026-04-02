"""SQLAlchemy async ORM models for the Digest service."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ArticleStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"
    skipped_teaser = "skipped_teaser"  # content too short, no full text available
    skipped_paywall = "skipped_paywall"  # classified as paywall/error page
    skipped_error = "skipped_error"  # classified as error page


class ContentQuality(str, enum.Enum):
    unknown = "unknown"
    full = "full"  # RSS provides full article content
    teaser = "teaser"  # RSS provides teaser, enrichment works
    paywall = "paywall"  # paywalled, enrichment fails


class FeedbackSource(str, enum.Enum):
    explicit = "explicit"
    click_through = "click_through"
    article_level = "article_level"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    oidc_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    oidc_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="user")  # 'admin' or 'user'
    role_source: Mapped[str] = mapped_column(
        String, default="auto"
    )  # 'auto', 'manual', 'oidc'
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    interest_weights: Mapped[list["InterestWeight"]] = relationship(
        back_populates="user"
    )
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="user")
    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user", uselist=False
    )


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    freshrss_feed_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, default="Uncategorized")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    content_quality: Mapped[str] = mapped_column(
        String, default=ContentQuality.unknown.value
    )
    quality_streak: Mapped[int] = mapped_column(
        Integer, default=0
    )  # consecutive same classification count
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    articles: Mapped[list["Article"]] = relationship(back_populates="feed")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    freshrss_item_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    feed_id: Mapped[int] = mapped_column(ForeignKey("feeds.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    digest_date: Mapped[str] = mapped_column(
        String, nullable=False
    )  # YYYY-MM-DD for browsing
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(ArticleStatus), default=ArticleStatus.pending
    )
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    feed: Mapped["Feed"] = relationship(back_populates="articles")
    sections: Mapped[list["Section"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    section_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    heading: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    topic_tags: Mapped[str] = mapped_column(
        Text, default=""
    )  # comma-separated; SQLite has no array type
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    is_surprise: Mapped[bool] = mapped_column(Boolean, default=False)
    has_humor: Mapped[bool] = mapped_column(Boolean, default=False)
    has_surprise_data: Mapped[bool] = mapped_column(Boolean, default=False)
    has_actionable_advice: Mapped[bool] = mapped_column(Boolean, default=False)
    reasoning: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # LLM's explanation of why this section matters
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    article: Mapped["Article"] = relationship(back_populates="sections")
    feedback_items: Mapped[list["Feedback"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )

    @property
    def tags_list(self) -> list[str]:
        """Parse comma-separated topic_tags into a list."""
        return [t.strip() for t in self.topic_tags.split(",") if t.strip()]

    @tags_list.setter
    def tags_list(self, tags: list[str]) -> None:
        self.topic_tags = ",".join(tags)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # +1 or -1
    source: Mapped[FeedbackSource] = mapped_column(
        Enum(FeedbackSource), default=FeedbackSource.explicit
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="feedback_items")
    section: Mapped["Section"] = relationship(back_populates="feedback_items")


class InterestWeight(Base):
    __tablename__ = "interest_weights"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    topic: Mapped[str] = mapped_column(String, primary_key=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="interest_weights")


class Setting(Base):
    """Key-value settings store. Runtime config lives here, not in files."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ProcessingLog(Base):
    __tablename__ = "processing_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id"), nullable=True
    )
    stage: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserProfile(Base):
    """Natural language interest profile maintained by the LLM."""

    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    profile_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    profile_version: Mapped[int] = mapped_column(Integer, default=1)
    pending_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    last_synthesized_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class ApiKey(Base):
    """API keys for Bearer token authentication."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String, nullable=False)  # first 8 chars
    key_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # SHA-256
    name: Mapped[str] = mapped_column(String, default="")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship()


class SectionScore(Base):
    """Cached per-user LLM-generated section scores."""

    __tablename__ = "section_scores"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
