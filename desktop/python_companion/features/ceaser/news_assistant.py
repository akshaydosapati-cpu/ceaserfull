import requests
from typing import Dict, Optional
import os

class NewsAssistant:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEWS_API_KEY") or os.getenv("GNEWS_API_KEY")
        self.provider = (os.getenv("NEWS_PROVIDER") or "newsapi").lower()
        self.base_url = (os.getenv("NEWS_API_BASE_URL") or ("https://newsapi.org/v2" if "newsapi" in self.provider else "https://gnews.io/api/v4")).rstrip("/")
        self.categories = [
            'general', 'world', 'nation', 'business', 'technology', 'entertainment',
            'sports', 'science', 'health'
        ]
        self.countries = {
            'us': 'United States', 'in': 'India', 'jp': 'Japan', 'cn': 'China', 'gb': 'United Kingdom',
            'ca': 'Canada', 'au': 'Australia', 'de': 'Germany', 'fr': 'France', 'br': 'Brazil',
            'ru': 'Russia', 'kr': 'South Korea', 'it': 'Italy', 'es': 'Spain', 'mx': 'Mexico',
            'sg': 'Singapore', 'ae': 'UAE', 'sa': 'Saudi Arabia', 'za': 'South Africa'
        }

    def get_top_headlines(self, country: str = "us", category: Optional[str] = None, num_headlines: int = 7) -> Dict:
        if not self.api_key:
            return {'success': False, 'error': "News API key is not configured", 'articles': []}
        if "newsapi" in self.provider or "newsapi.org" in self.base_url:
            return self._newsapi_top_headlines(country, category, num_headlines)
        url = f"{self.base_url}/top-headlines"
        params = {
            'apikey': self.api_key,
            'lang': 'en',
            'country': country or 'us',
            'max': num_headlines
        }
        if category and category in self.categories:
            params['category'] = category
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("articles"):
                articles = []
                for article in data["articles"]:
                    article_info = {
                        'title': article.get('title', 'No title'),
                        'description': article.get('description', 'No description'),
                        'url': article.get('url', ''),
                        'source': article.get('source', {}).get('name', 'Unknown'),
                        'published_at': article.get('publishedAt', ''),
                        'content': article.get('content', ''),
                        'url_to_image': article.get('image', '')
                    }
                    articles.append(article_info)
                return {
                    'success': True,
                    'query': f"top headlines {category or ''} {country}",
                    'total_results': len(articles),
                    'articles': articles
                }
            else:
                return {'success': False, 'error': f"GNews API error: {data.get('errors', 'Unknown error')}", 'articles': []}
        except Exception as e:
            return {'success': False, 'error': str(e), 'articles': []}

    def search_news(self, query: str, language: str = "en", country: Optional[str] = None, num_results: int = 10) -> Dict:
        if not self.api_key:
            return {'success': False, 'error': "News API key is not configured", 'articles': []}
        if "newsapi" in self.provider or "newsapi.org" in self.base_url:
            return self._newsapi_search(query, language, country, num_results)
        url = f"{self.base_url}/search"
        params = {
            'apikey': self.api_key,
            'q': query,
            'lang': language,
            'max': num_results
        }
        if country is not None:
            params['country'] = country or 'us'
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("articles"):
                articles = []
                for article in data["articles"]:
                    article_info = {
                        'title': article.get('title', 'No title'),
                        'description': article.get('description', 'No description'),
                        'url': article.get('url', ''),
                        'source': article.get('source', {}).get('name', 'Unknown'),
                        'published_at': article.get('publishedAt', ''),
                        'content': article.get('content', ''),
                        'url_to_image': article.get('image', '')
                    }
                    articles.append(article_info)
                return {
                    'success': True,
                    'query': query,
                    'total_results': len(articles),
                    'articles': articles
                }
            else:
                return {'success': False, 'error': f"GNews API error: {data.get('errors', 'Unknown error')}", 'articles': []}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f"Network error: {str(e)}", 'articles': []}
        except Exception as e:
            return {'success': False, 'error': f"Unexpected error: {str(e)}", 'articles': []}

    def _normalize_newsapi_article(self, article: Dict) -> Dict:
        return {
            'title': article.get('title') or 'No title',
            'description': article.get('description') or 'No description',
            'url': article.get('url') or '',
            'source': (article.get('source') or {}).get('name') or 'Unknown',
            'published_at': article.get('publishedAt') or '',
            'content': article.get('content') or '',
            'url_to_image': article.get('urlToImage') or ''
        }

    def _newsapi_top_headlines(self, country: str = "us", category: Optional[str] = None, num_headlines: int = 7) -> Dict:
        params = {
            'apiKey': self.api_key,
            'country': (country or os.getenv("NEWS_DEFAULT_REGION") or "us").lower(),
            'pageSize': num_headlines,
        }
        if category and category in self.categories:
            params['category'] = category
        try:
            response = requests.get(f"{self.base_url}/top-headlines", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            articles = [self._normalize_newsapi_article(item) for item in data.get("articles", [])]
            return {'success': bool(articles), 'query': f"top headlines {category or ''} {country}", 'total_results': len(articles), 'articles': articles, 'error': "" if articles else data.get("message", "No news found")}
        except Exception as e:
            return {'success': False, 'error': str(e), 'articles': []}

    def _newsapi_search(self, query: str, language: str = "en", country: Optional[str] = None, num_results: int = 10) -> Dict:
        params = {
            'apiKey': self.api_key,
            'q': query,
            'language': language or os.getenv("NEWS_DEFAULT_LANGUAGE") or "en",
            'pageSize': num_results,
            'sortBy': 'publishedAt',
        }
        try:
            response = requests.get(f"{self.base_url}/everything", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            articles = [self._normalize_newsapi_article(item) for item in data.get("articles", [])]
            return {'success': bool(articles), 'query': query, 'total_results': len(articles), 'articles': articles, 'error': "" if articles else data.get("message", "No news found")}
        except Exception as e:
            return {'success': False, 'error': str(e), 'articles': []}

    def get_news_by_category(self, category: str, country: str = "us", num_headlines: int = 7) -> Dict:
        """Get news for a specific category"""
        if category not in self.categories:
            return {'success': False, 'error': f"Invalid category. Available: {', '.join(self.categories)}"}
        return self.get_top_headlines(country, category, num_headlines)
    
    def get_news_by_country(self, country: str, category: Optional[str] = None, 
                          num_headlines: int = 7) -> Dict:
        """Get news for a specific country"""
        if country not in self.countries:
            return {'success': False, 'error': f"Invalid country code. Available: {', '.join(self.countries.keys())}"}
        
        return self.get_top_headlines(country, category, num_headlines)
    
    def get_latest_news(self, hours: int = 24, num_results: int = 7) -> Dict:
        """Get latest news from the past specified hours"""
        # Calculate date range
        # GNews does not support date range search directly in their API.
        # This method will return top headlines for the current date.
        return self.get_top_headlines(num_headlines=num_results)
    
    def get_trending_topics(self, country: str = "us", num_topics: int = 5) -> Dict:
        """Get trending topics by analyzing recent headlines"""
        headlines = self.get_top_headlines(country, num_headlines=20)
        
        if not headlines['success']:
            return headlines
        
        # Extract common words/phrases from headlines
        word_count = {}
        for article in headlines['articles']:
            title = article['title'].lower()
            # Remove common words and punctuation
            # GNews does not provide direct word frequency, so this part is simplified.
            # For a more accurate trending, a different approach would be needed.
            # For now, we'll just count words that are not common terms.
            words = [w for w in title.split() if len(w) > 3 and w.isalpha()]
            for word in words:
                if word not in ['news', 'says', 'will', 'have', 'with', 'this', 'that', 'they', 'their']:
                    word_count[word] = word_count.get(word, 0) + 1
        
        # Get top trending words
        trending = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:num_topics]
        
        return {
            'success': True,
            'country': headlines['country'],
            'trending_topics': [topic[0] for topic in trending],
            'topic_counts': dict(trending)
        }
    
    def format_headlines_report(self, news_data: Dict) -> str:
        if not news_data.get('success'):
            return f"Sorry, I couldn't fetch the news: {news_data.get('error', 'Unknown error')}"
        articles = news_data['articles']
        if not articles:
            return "No news articles found."
        report = "Top headlines:\n\n"
        for i, article in enumerate(articles, 1):
            report += f"{i}. {article['title']}\n   Source: {article['source']}\n"
            if article['description'] and article['description'] != 'No description':
                desc = article['description'][:150] + "..." if len(article['description']) > 150 else article['description']
                report += f"   {desc}\n"
            report += "\n"
        return report
    
    def format_news_summary(self, news_data: Dict) -> str:
        if not news_data['success']:
            return f"Sorry, I couldn't fetch the news: {news_data['error']}"
        articles = news_data['articles']
        if not articles:
            return "No news articles found."
        # Only include the headlines (titles), not extra matter
        summary = "; ".join([f"{a['title']}" for a in articles])
        return summary

    def format_search_results(self, search_data: Dict) -> str:
        if not search_data['success']:
            return f"Sorry, I couldn't fetch the news: {search_data['error']}"
        articles = search_data['articles']
        if not articles:
            return "No news articles found."
        summary = f"Found {len(articles)} articles for '{search_data.get('query', '')}':\n"
        for i, a in enumerate(articles[:5], 1):
            summary += f"\n{i}. {a['title'][:50]}..."
        return summary
    
    def get_news_categories(self) -> str:
        """Get list of available news categories"""
        return f"Available news categories: {', '.join(self.categories)}"
    
    def get_news_countries(self) -> str:
        """Get list of available countries"""
        country_list = [f"{code} ({name})" for code, name in self.countries.items()]
        return f"Available countries: {', '.join(country_list)}"
    
    def get_comprehensive_news(self, country: str = "us") -> str:
        """Get comprehensive news report with multiple categories"""
        categories = ['general', 'technology', 'business', 'sports']
        all_news = []
        
        for category in categories:
            news = self.get_news_by_category(category, country, 2)
            if news['success']:
                all_news.append(f"\n{category.upper()} NEWS:")
                for article in news['articles']:
                    title = article['title']
                    # GNews does not have a direct source suffix like NewsAPI, so we'll just use the title.
                    all_news.append(f"• {title}")
        
        if all_news:
            return f"Comprehensive news from {self.countries.get(country, country)}:" + "".join(all_news)
        else:
            return f"Sorry, I couldn't fetch comprehensive news for {country}." 
