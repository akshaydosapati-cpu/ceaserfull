from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from time import perf_counter
from urllib.parse import urlparse

from app.engines.research_engine.page_extractor import PageExtractor
from app.engines.research_engine.schemas import ResearchSource
from app.engines.research_engine.search_provider import SearchProvider, SerperSearchProvider


logger = logging.getLogger(__name__)


class SourceCollector:
    MAX_EXTRACTED_SOURCES = 3
    EXTRACTION_WORKERS = 3

    def __init__(self, provider: SearchProvider | None = None, page_extractor: PageExtractor | None = None):
        self.provider = provider or SerperSearchProvider()
        self.page_extractor = page_extractor or PageExtractor(timeout_seconds=3.5)
        self.last_timings: dict[str, float] = {}

    def collect_sources(self, query: str, limit: int = 6) -> list[ResearchSource]:
        started = perf_counter()
        raw_sources = self.provider.search(query=query, limit=limit * 2)
        searched = perf_counter()
        deduped: dict[str, ResearchSource] = {}
        for raw in raw_sources:
            url = raw.get("url", "")
            if not url or url in deduped:
                continue
            source = ResearchSource(
                title=raw.get("title") or url,
                url=url,
                source=raw.get("source") or self._host(url),
                snippet=raw.get("snippet") or "",
                image_url=raw.get("image_url"),
                score=self._score(query=query, title=raw.get("title", ""), snippet=raw.get("snippet", ""), url=url),
            )
            deduped[url] = source
        ranked_sources = sorted(deduped.values(), key=lambda item: item.score, reverse=True)[:limit]
        ranked = perf_counter()
        extraction_targets = ranked_sources[: self.MAX_EXTRACTED_SOURCES]
        if extraction_targets:
            executor = ThreadPoolExecutor(max_workers=min(self.EXTRACTION_WORKERS, len(extraction_targets)), thread_name_prefix="ceaser-research")
            futures = {executor.submit(self.page_extractor.extract, source.url, query): source for source in extraction_targets}
            try:
                for future in as_completed(futures):
                    source = futures[future]
                    try:
                        extracted = future.result()
                    except Exception:  # noqa: BLE001 - one source must not fail the research request.
                        logger.debug("research_source_extraction_failed host=%s", self._host(source.url), exc_info=True)
                        continue
                    if not extracted:
                        continue
                    source.excerpt = extracted.excerpt
                    source.publisher = extracted.publisher
                    source.retrieved_at = extracted.retrieved_at
                    source.image_url = source.image_url or extracted.image_url
                    if extracted.title and (not source.title or source.title == source.url):
                        source.title = extracted.title
                    if extracted.excerpt:
                        source.snippet = extracted.excerpt[:500]
                        source.score += 2
            finally:
                executor.shutdown(wait=True, cancel_futures=True)
        finished = perf_counter()
        self.last_timings = {
            "search_ms": round((searched - started) * 1000, 2),
            "ranking_ms": round((ranked - searched) * 1000, 2),
            "extraction_ms": round((finished - ranked) * 1000, 2),
            "sources_returned": float(len(ranked_sources)),
            "sources_extracted": float(len(extraction_targets)),
        }
        logger.info(
            "ceaser_research_timing search_ms=%s ranking_ms=%s extraction_ms=%s sources_returned=%s sources_extracted=%s",
            self.last_timings["search_ms"], self.last_timings["ranking_ms"], self.last_timings["extraction_ms"],
            len(ranked_sources), len(extraction_targets),
        )
        return sorted(ranked_sources, key=lambda item: item.score, reverse=True)

    def collect_images(self, query: str, limit: int = 3) -> list[dict]:
        search_images = getattr(self.provider, "search_images", None)
        return search_images(query=query, limit=limit) if callable(search_images) else []

    def _score(self, query: str, title: str, snippet: str, url: str) -> float:
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        content = f"{title} {snippet}".lower()
        relevance = sum(1 for term in query_terms if term in content) * 3
        authority = 2 if any(domain in url for domain in ["who.int", "nih.gov", "gov", "edu", "wikipedia.org"]) else 1
        freshness = 1 if any(term in content for term in ["2026", "2025", "latest", "recent"]) else 0
        return relevance + authority + freshness

    def _host(self, url: str) -> str:
        return urlparse(url).netloc.replace("www.", "")
