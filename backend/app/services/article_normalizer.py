"""
Article Normalizer for Pulse News Intelligence.
Cleans and standardizes raw RSS/Atom entries into canonical Article objects.
"""
import re
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "fbclid", "gclid", "mc_cid", "mc_eid", "source", "feed"
}

HTML_TAG_REGEX = re.compile(r"<[^>]+>")

def strip_html_tags(html_text: Optional[str]) -> str:
    """Removes HTML markup and collapses extra whitespace."""
    if not html_text:
        return ""
    text = HTML_TAG_REGEX.sub(" ", html_text)
    # Replace common HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(text.split()).strip()

def normalize_canonical_url(url: Optional[str]) -> str:
    """
    Normalizes URLs by:
    - Lowercasing scheme and network location.
    - Stripping marketing/tracking query parameters (utm_*, ref, etc.).
    - Removing trailing slashes (except for root domain).
    """
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
        
        # Filter tracking query parameters
        filtered_queries = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in TRACKING_QUERY_PARAMS
        ]
        query = urlencode(filtered_queries)
        
        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception:
        return url.strip()

def parse_published_time(entry: Any) -> datetime:
    """
    Extracts published datetime from feed entry.
    Falls back to current UTC datetime if missing or unparseable.
    """
    # 1. feedparser parsed time tuple
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        t_struct = getattr(entry, field, None)
        if t_struct:
            try:
                return datetime(*t_struct[:6])
            except Exception:
                pass

    # 2. String timestamp parsing
    for field in ("published", "pubDate", "updated", "date"):
        val = getattr(entry, field, None)
        if isinstance(val, str) and val.strip():
            # Standard formats
            for fmt in (
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y %H:%M:%S %z",
            ):
                try:
                    return datetime.strptime(val.strip(), fmt)
                except Exception:
                    continue

    return datetime.utcnow()

def extract_image_url(entry: Any) -> Optional[str]:
    """Finds image URL in media_content, enclosures, or links."""
    # Media content
    media = getattr(entry, "media_content", None)
    if media and isinstance(media, list) and len(media) > 0:
        url = media[0].get("url")
        if url:
            return url

    # Enclosures
    enclosures = getattr(entry, "enclosures", None)
    if enclosures and isinstance(enclosures, list) and len(enclosures) > 0:
        for enc in enclosures:
            if enc.get("type", "").startswith("image/"):
                return enc.get("href") or enc.get("url")

    # Links
    links = getattr(entry, "links", None)
    if links and isinstance(links, list):
        for link in links:
            if link.get("type", "").startswith("image/"):
                return link.get("href")

    return None

class ArticleNormalizer:
    @staticmethod
    def normalize_entry(raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        entry = raw_item["raw_entry"]
        source_id = raw_item["source_id"]
        source_name = raw_item["source_name"]
        source_base = raw_item["source_base_url"]
        category = raw_item["category"]

        title = getattr(entry, "title", "").strip()
        if not title:
            return None

        # Clean title
        title = strip_html_tags(title)

        # Raw URL
        raw_url = getattr(entry, "link", "").strip()
        if not raw_url:
            return None

        canonical_url = normalize_canonical_url(raw_url)
        if not canonical_url:
            return None

        # External ID / GUID
        external_id = getattr(entry, "id", None) or getattr(entry, "guid", None) or canonical_url
        if isinstance(external_id, dict):
            external_id = external_id.get("text", canonical_url)

        # Summary / Description
        summary_raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
        summary = strip_html_tags(summary_raw)
        if not summary:
            summary = f"Reporting by {source_name}: {title}"
        if len(summary) > 1000:
            summary = summary[:997] + "..."

        # Published date
        published_dt = parse_published_time(entry)

        # Author
        author = getattr(entry, "author", None)
        if author:
            author = strip_html_tags(author)

        # Image URL
        image_url = extract_image_url(entry)

        # Content hash
        content_hash = hashlib.sha256(f"{source_id}:{canonical_url}".encode("utf-8")).hexdigest()
        article_id = f"art-{content_hash[:16]}"

        parsed_netloc = urlparse(canonical_url).netloc

        return {
            "id": article_id,
            "external_id": str(external_id),
            "source_id": source_id,
            "source_name": source_name,
            "source_domain": parsed_netloc or source_base,
            "title": title,
            "description": summary,
            "url": raw_url,
            "canonical_url": canonical_url,
            "author": author,
            "category": category,
            "primary_topic": raw_item.get("primary_topic", "Technology"),
            "image_url": image_url,
            "published_at": published_dt.isoformat(),
            "raw_content_hash": content_hash,
            "reliability_score": raw_item.get("reliability_score", 0.9)
        }

article_normalizer = ArticleNormalizer()
