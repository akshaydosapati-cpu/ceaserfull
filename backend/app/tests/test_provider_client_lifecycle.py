import asyncio

from app.intelligence.ai.llm.openai_provider import OpenAIProvider


def test_provider_reuses_and_closes_http_client():
    async def verify():
        provider = OpenAIProvider()
        first = provider.http_client
        assert provider.http_client is first

        await provider.aclose()
        assert first.is_closed

        replacement = provider.http_client
        assert replacement is not first
        await provider.aclose()

    asyncio.run(verify())
