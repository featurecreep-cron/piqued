"""RSS feed output — above-threshold sections as an RSS feed."""

import logging
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from piqued.api.v1.auth import get_api_user
from piqued.db import get_session
from piqued.models import User
from piqued.web.data import get_home_sections

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/feed.xml")
async def rss_feed(
    date: str | None = None,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    """RSS feed of above-threshold sections for the authenticated user."""
    data = await get_home_sections(user, date, session)
    threshold = data["threshold"]

    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = f"Piqued — {user.username}"
    SubElement(channel, "description").text = "Personalized article sections from Piqued"
    SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    for section, article, confidence, reasoning in data["all_sections"]:
        if confidence < threshold and section.id not in data["surprise_ids"]:
            continue

        item = SubElement(channel, "item")
        title = section.heading or article.title
        if section.heading:
            title = f"{article.title} — {section.heading}"
        SubElement(item, "title").text = title
        if article.url:
            SubElement(item, "link").text = article.url
        SubElement(item, "description").text = section.summary
        if article.published_at:
            SubElement(item, "pubDate").text = article.published_at.strftime(
                "%a, %d %b %Y %H:%M:%S +0000"
            )
        SubElement(item, "guid", isPermaLink="false").text = f"piqued-section-{section.id}"

        tags = section.tags_list
        for tag in tags:
            SubElement(item, "category").text = tag

    xml_bytes = tostring(rss, encoding="unicode", xml_declaration=False)
    xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes
    return Response(content=xml_out, media_type="application/rss+xml")
