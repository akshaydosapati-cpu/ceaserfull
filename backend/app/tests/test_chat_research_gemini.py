import os
import time
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database.base import Base
from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user
from app.engines.research_engine.engine import ResearchEngine
from app.engines.research_engine.page_extractor import ExtractedPage, PageExtractor
from app.engines.research_engine.schemas import ResearchResult, ResearchSource
from app.engines.research_engine.search_provider import DuckDuckGoSearchProvider, SerperSearchProvider
from app.engines.research_engine.source_collector import SourceCollector
from app.services.orchestrator.knowledge_router import KnowledgeRoute, KnowledgeRouter
from app.main import create_app
from app.models.user import User
from app.services.conversation_service import ConversationService
from app.services.llm.gemini_provider import GeminiProvider


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_current_user() -> User:
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "chat-research@example.com").first()
    if not user:
        user = User(email="chat-research@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    db.close()
    return user


Base.metadata.create_all(bind=engine)
app = create_app()
app.dependency_overrides[get_db] = override_db
app.dependency_overrides[get_current_user] = override_current_user
client = TestClient(app)


class FakeSearchProvider:
    def search(self, query: str, limit: int = 6) -> list[dict]:
        return [
            {
                "title": "AI healthcare startups in India 2025",
                "url": "https://example.com/healthcare-ai-india",
                "source": "Example",
                "snippet": "AI healthcare startups in India are growing across clinics and diagnostics.",
            },
            {
                "title": "Duplicate",
                "url": "https://example.com/healthcare-ai-india",
                "source": "Example",
                "snippet": "Duplicate source",
            },
            {
                "title": "General startup report",
                "url": "https://example.com/startups",
                "source": "Example",
                "snippet": "General startup ecosystem context.",
            },
        ][:limit]


class EmptySearchProvider:
    def search(self, query: str, limit: int = 6) -> list[dict]:
        return []


def current_user_dict() -> dict:
    user = override_current_user()
    return {"id": user.id, "email": user.email}


def test_conversation_title_and_message_persistence() -> None:
    conversation = client.post("/conversations", json={}).json()

    response = client.post(
        "/ceaser/chat",
        json={
            "conversation_id": conversation["id"],
            "message": "Build healthcare startup",
        },
    )

    assert response.status_code == 200
    db = TestingSessionLocal()
    restored = ConversationService(db).get(conversation["id"])
    messages = ConversationService(db).list_messages(conversation_id=conversation["id"])
    db.close()

    assert restored.title == "Healthcare Startup"
    assert [message.role for message in messages] == ["user", "assistant"]


def test_research_source_collection_deduplicates_and_ranks() -> None:
    sources = SourceCollector(provider=FakeSearchProvider()).collect_sources("AI healthcare startups in India")

    assert len(sources) == 2
    assert sources[0].url == "https://example.com/healthcare-ai-india"
    assert sources[0].score >= sources[1].score


def test_research_engine_builds_citations() -> None:
    result = ResearchEngine(source_collector=SourceCollector(provider=FakeSearchProvider())).research("AI healthcare startups in India")

    assert result.summary
    assert result.key_findings
    assert result.citations[0].url == result.sources[0].url


def test_research_engine_does_not_create_fake_search_source() -> None:
    result = ResearchEngine(source_collector=SourceCollector(provider=EmptySearchProvider())).research("Clinilocker")

    assert result.sources == []
    assert result.citations == []
    assert "No live sources" in result.summary


def test_page_extractor_uses_safe_open_graph_image_only() -> None:
    extractor = PageExtractor()
    html = '<meta property="og:image" content="/images/preview.jpg"><meta name="twitter:image" content="javascript:alert(1)">'

    assert extractor._image_url(html, "https://example.com/article") == "https://example.com/images/preview.jpg"


def test_stable_factual_question_uses_direct_chat() -> None:
    decision = KnowledgeRouter().classify(
        message="What are the war machines India has?",
        has_attached_files=False,
        is_follow_up=False,
    )

    assert decision.route is KnowledgeRoute.GENERAL


def test_freshness_signal_overrides_follow_up_route() -> None:
    decision = KnowledgeRouter().classify(
        message="What is the latest AI news today?",
        has_attached_files=False,
        is_follow_up=True,
    )

    assert decision.route is KnowledgeRoute.RESEARCH


def test_stable_follow_up_remains_conversation_route() -> None:
    decision = KnowledgeRouter().classify(
        message="Explain that in simpler words.",
        has_attached_files=False,
        is_follow_up=True,
    )

    assert decision.route is KnowledgeRoute.FOLLOW_UP


def test_emerging_model_name_uses_live_research() -> None:
    decision = KnowledgeRouter().classify(
        message="What do you know about GPT-6 Astra?",
        has_attached_files=False,
        is_follow_up=False,
    )

    assert decision.route is KnowledgeRoute.RESEARCH


def test_knowledge_cutoff_follow_up_uses_live_research() -> None:
    decision = KnowledgeRouter().classify(
        message="Just tell me till which year you have data.",
        has_attached_files=False,
        is_follow_up=True,
    )

    assert decision.route is KnowledgeRoute.RESEARCH


def test_likely_gpt_typo_uses_live_research() -> None:
    decision = KnowledgeRouter().classify(
        message="What do you know about got 6 Astra?",
        has_attached_files=False,
        is_follow_up=False,
    )

    assert decision.route is KnowledgeRoute.RESEARCH


def test_emerging_model_research_query_preserves_full_name() -> None:
    from app.services.orchestrator.orchestrator import CeaserOrchestrator

    orchestrator = CeaserOrchestrator.__new__(CeaserOrchestrator)

    assert orchestrator._research_query("What do you know about GPT-6 Astra?") == "GPT-6 Astra"
    assert orchestrator._research_query("What do you know about got 6 Astra?") == "GPT 6 Astra"


def test_latest_gpt_release_builds_specific_live_query() -> None:
    from app.services.orchestrator.orchestrator import CeaserOrchestrator

    orchestrator = CeaserOrchestrator.__new__(CeaserOrchestrator)

    assert orchestrator._research_query("What do you know about the latest release of GPT model 2026?") == (
        "GPT model 2026 latest release official"
    )


def test_latest_release_query_is_entity_agnostic() -> None:
    from app.services.orchestrator.orchestrator import CeaserOrchestrator

    orchestrator = CeaserOrchestrator.__new__(CeaserOrchestrator)

    assert orchestrator._research_query("What is the latest release of Gemini model 2026?") == (
        "Gemini model 2026 latest release official"
    )
    assert orchestrator._research_query("Tell me the newest release of Acme Platform?") == (
        "Acme Platform latest release official"
    )
    assert orchestrator._research_query("What are the latest Tesla earnings in 2026?") == (
        "latest Tesla earnings in 2026"
    )


def test_corporate_acquisition_routes_to_research_with_both_companies() -> None:
    from app.services.orchestrator.orchestrator import CeaserOrchestrator

    message = "Do you know anything about NVIDIA aquisition of Hugging Face?"
    decision = KnowledgeRouter().classify(message=message, has_attached_files=False, is_follow_up=False)
    orchestrator = CeaserOrchestrator.__new__(CeaserOrchestrator)

    assert decision.route is KnowledgeRoute.RESEARCH
    assert orchestrator._research_query(message) == "NVIDIA acquisition of Hugging Face latest official"


def test_acquisition_concept_question_stays_general() -> None:
    decision = KnowledgeRouter().classify(
        message="Explain acquisition accounting in simple terms.",
        has_attached_files=False,
        is_follow_up=False,
    )

    assert decision.route is KnowledgeRoute.GENERAL


def test_live_event_flows_from_classification_into_llm_prompt(monkeypatch) -> None:
    from app.services.orchestrator.orchestrator import CeaserOrchestrator

    db = TestingSessionLocal()
    user = override_current_user()
    orchestrator = CeaserOrchestrator(db)
    queries: list[str] = []

    def fake_research(query: str, selected_agent_names: list[str]) -> ResearchResult:
        queries.append(query)
        return ResearchResult(
            query=query,
            summary="Collected current evidence.",
            key_findings=["NVIDIA announced an acquisition of Hugging Face."],
            sources=[
                ResearchSource(
                    title="NVIDIA to Acquire Hugging Face",
                    url="https://blogs.nvidia.com/example",
                    source="NVIDIA",
                    snippet="Official announcement",
                    score=10,
                )
            ],
            citations=[],
            images=[],
        )

    monkeypatch.setattr(orchestrator, "_maybe_research", fake_research)
    prepared = orchestrator.prepare_stream_request(
        user_id=user.id,
        message="Do you know anything about NVIDIA acquisition of Hugging Face?",
        request_id="live-event-flow",
    )
    instructions, prompt = orchestrator.response_pipeline._build_prompt(
        message=prepared["message"],
        context=prepared["context"],
    )
    db.close()

    assert prepared["observability"]["knowledge_route"] == "research"
    assert prepared["observability"]["web_search_requested"] is True
    assert queries == ["NVIDIA acquisition of Hugging Face latest official"]
    assert "treat its sources as the authority" in instructions
    assert "NVIDIA to Acquire Hugging Face" in prompt
    assert "Official announcement" in prompt


def test_serper_search_returns_ranked_results_and_images(monkeypatch) -> None:
    class Response:
        def __init__(self, payload: dict):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.payload

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json, timeout):
            assert headers["X-API-KEY"] == "test-key"
            assert json["q"] == "India defence"
            if url.endswith("/images"):
                return Response({"images": [{"title": "Indian tank", "link": "https://example.com/tank", "imageUrl": "https://images.example.com/tank.jpg", "source": "Example"}]})
            return Response({"organic": [{"title": "India defence", "link": "https://example.com/defence", "domain": "example.com", "snippet": "Defence overview"}]})

    monkeypatch.setattr("app.engines.research_engine.search_provider.research_http_client", lambda: Client())
    provider = SerperSearchProvider(api_key="test-key")
    sources = provider.search("India defence", limit=3)
    images = provider.search_images("India defence", limit=3)

    assert sources[0]["url"] == "https://example.com/defence"
    assert images[0]["image_url"] == "https://images.example.com/tank.jpg"


def test_source_extraction_is_bounded_concurrent_and_keeps_all_ranked_sources() -> None:
    class ManySources:
        def search(self, query: str, limit: int = 6) -> list[dict]:
            return [
                {"title": f"Current evidence {index}", "url": f"https://example.com/{index}", "source": "Example", "snippet": f"Relevant 2026 evidence {index}"}
                for index in range(6)
            ]

        def search_images(self, query: str, limit: int = 3) -> list[dict]:
            return []

    class SlowExtractor:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def extract(self, url: str, query: str) -> ExtractedPage:
            self.urls.append(url)
            time.sleep(0.12)
            return ExtractedPage(url=url, title=None, publisher="Example", excerpt="Verified evidence", retrieved_at="now")

    extractor = SlowExtractor()
    collector = SourceCollector(provider=ManySources(), page_extractor=extractor)
    started = time.perf_counter()
    sources = collector.collect_sources("current evidence 2026")
    elapsed = time.perf_counter() - started

    assert len(sources) == 6
    assert len(extractor.urls) == 3
    assert elapsed < 0.28
    assert collector.last_timings["sources_extracted"] == 3


def test_failed_source_does_not_discard_other_research_evidence() -> None:
    class Sources:
        def search(self, query: str, limit: int = 6) -> list[dict]:
            return [
                {"title": f"Evidence {index}", "url": f"https://example.com/{index}", "source": "Example", "snippet": f"Usable snippet {index}"}
                for index in range(3)
            ]

        def search_images(self, query: str, limit: int = 3) -> list[dict]:
            return []

    class PartialExtractor:
        def extract(self, url: str, query: str) -> ExtractedPage | None:
            if url.endswith("/1"):
                raise TimeoutError("slow source")
            return ExtractedPage(url=url, title=None, publisher="Example", excerpt="Extracted evidence", retrieved_at="now")

    result = ResearchEngine(source_collector=SourceCollector(provider=Sources(), page_extractor=PartialExtractor())).research(
        "current evidence 2026",
        include_images=False,
    )

    assert len(result.sources) == 3
    assert any(source.snippet == "Usable snippet 1" for source in result.sources)
    assert sum(bool(source.excerpt) for source in result.sources) == 2
    assert result.timings["extraction_ms"] >= 0


def test_visual_research_loads_sources_and_images_concurrently() -> None:
    class Collector:
        last_timings = {"search_ms": 1.0, "ranking_ms": 1.0, "extraction_ms": 1.0}

        def collect_sources(self, query: str) -> list[ResearchSource]:
            time.sleep(0.12)
            return [ResearchSource(title="Source", url="https://example.com", source="Example", snippet="Evidence")]

        def collect_images(self, query: str) -> list[dict]:
            time.sleep(0.12)
            return [{"title": "Image", "url": "https://example.com", "image_url": "https://example.com/image.jpg", "source": "Example"}]

    started = time.perf_counter()
    result = ResearchEngine(source_collector=Collector()).research("visual topic", include_images=True)
    elapsed = time.perf_counter() - started

    assert len(result.sources) == 1
    assert len(result.images) == 1
    assert elapsed < 0.22


def test_duckduckgo_provider_does_not_fallback_to_search_url(monkeypatch) -> None:
    def raise_error(*args, **kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(DuckDuckGoSearchProvider, "_search_html", lambda self, query, limit: [])
    provider = DuckDuckGoSearchProvider()
    monkeypatch.setattr("httpx.Client.get", raise_error)

    assert provider.search("Clinilocker") == []


def test_research_endpoint(monkeypatch) -> None:
    def fake_research(self, query: str) -> ResearchResult:
        return ResearchResult(
            query=query,
            summary="Collected one ranked source.",
            key_findings=["Finding"],
            sources=[
                ResearchSource(
                    title="Source",
                    url="https://example.com",
                    source="Example",
                    snippet="Snippet",
                    score=3,
                )
            ],
            citations=[{"title": "Source", "url": "https://example.com"}],
        )

    monkeypatch.setattr(ResearchEngine, "research", fake_research)
    response = client.post("/research", json={"query": "AI healthcare startups in India"})

    assert response.status_code == 200
    assert response.json()["sources"][0]["url"] == "https://example.com"


def test_gemini_missing_key_falls_back_to_merged_contributions() -> None:
    response = GeminiProvider().generate_response(
        "Build startup",
        {"merged_contributions": {"response": "Merged contribution response"}},
    )

    assert "Executive Summary" in response
    assert "Gemini key is missing" in response
    assert "Merged contribution response" not in response
