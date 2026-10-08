from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from app.engines.research_engine.citation_builder import CitationBuilder
from app.engines.research_engine.schemas import ResearchImage, ResearchResult
from app.engines.research_engine.source_collector import SourceCollector


class ResearchEngine:
    def __init__(self, source_collector: SourceCollector | None = None, citation_builder: CitationBuilder | None = None):
        self.source_collector = source_collector or SourceCollector()
        self.citation_builder = citation_builder or CitationBuilder()

    def research(self, query: str, *, include_images: bool = True) -> ResearchResult:
        started = perf_counter()
        image_rows: list[dict] = []
        if include_images:
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="ceaser-research-prepare") as executor:
                source_future = executor.submit(self.source_collector.collect_sources, query=query)
                image_future = executor.submit(self.source_collector.collect_images, query=query)
                sources = source_future.result()
                image_rows = image_future.result()
        else:
            sources = self.source_collector.collect_sources(query=query)
        sources_ready = perf_counter()
        images = [ResearchImage(**image) for image in image_rows]
        citations = self.citation_builder.build(sources)
        key_findings = [source.excerpt or source.snippet for source in sources if source.excerpt or source.snippet][:5]
        summary = self._summary(query=query, key_findings=key_findings, source_count=len(sources))
        finished = perf_counter()
        timings = dict(getattr(self.source_collector, "last_timings", {}))
        timings.update(
            research_assembly_ms=round((finished - sources_ready) * 1000, 2),
            research_total_ms=round((finished - started) * 1000, 2),
        )
        return ResearchResult(
            query=query,
            summary=summary,
            key_findings=key_findings,
            sources=sources,
            citations=citations,
            images=images,
            timings=timings,
        )

    def _summary(self, query: str, key_findings: list[str], source_count: int) -> str:
        if not source_count:
            return f"No live sources were found for '{query}'. CEASER can still reason from memory and agent context."
        return f"Collected {source_count} ranked sources for '{query}' and prepared citation-backed research context."
