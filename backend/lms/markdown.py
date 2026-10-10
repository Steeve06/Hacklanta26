import bleach
import markdown as md
from django.core.cache import cache

ALLOWED_TAGS = [
    "p", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote",
    "a", "table", "thead", "tbody", "tr", "th", "td", "hr", "br",
]  # fmt: skip
ALLOWED_ATTRS = {"a": ["href", "title"]}


def render_markdown(source: str, cache_key: str | None = None) -> str:
    if cache_key:
        cached = cache.get(f"md:{cache_key}")
        if cached is not None:
            return cached
    html = md.markdown(source, extensions=["tables", "fenced_code"])
    clean = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    clean = bleach.linkify(clean, callbacks=[_external_link])
    if cache_key:
        cache.set(f"md:{cache_key}", clean, 60 * 60 * 24)
    return clean


def _external_link(attrs, new=False):
    attrs[(None, "rel")] = "noopener noreferrer"
    return attrs
