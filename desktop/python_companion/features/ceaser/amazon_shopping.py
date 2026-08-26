import requests
import os
from typing import Optional, List, Dict, Any
import json
import time
import webbrowser
import subprocess
import urllib.parse
import sqlite3
from datetime import datetime

# Load environment variables directly

class AmazonShopping:
    def __init__(self):
        self.api_key = os.getenv('RAPIDAPI_KEY')
        self.base_url = "https://amazon-data-scraper-api3.p.rapidapi.com"
        self.headers = {
            'X-RapidAPI-Key': self.api_key,
            'X-RapidAPI-Host': 'amazon-data-scraper-api3.p.rapidapi.com'
        }
        self.db_path = 'amazon_shopping.db'
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for price tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT NOT NULL,
                product_title TEXT,
                current_price REAL,
                currency TEXT DEFAULT 'USD',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_note TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def _make_request(self, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to Amazon API"""
        if not self.api_key:
            print("[ERROR] RapidAPI key not found. Please set RAPIDAPI_KEY in .env file")
            return None
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Amazon API request failed: {e}")
            return None
    
    def open_amazon_search(self, query: str):
        """Open the Amazon search results page in the default web browser."""
        search_query = query.replace(' ', '+')
        url = f"https://www.amazon.com/s?k={search_query}"
        webbrowser.open(url)
        return url
    
    def search_products(self, query: str, location: str = "90210", limit: int = 5, open_browser: bool = False) -> Optional[List[Dict]]:
        """Search for products on Amazon and optionally open the browser."""
        if open_browser:
            base_url = "https://www.amazon.com/s"
            params = {"k": query}
            url = f"{base_url}?{urllib.parse.urlencode(params)}"
            try:
                opened = webbrowser.open_new_tab(url)
                if not opened:
                    try:
                        os.startfile(url)
                        print(f"Opened Amazon search for '{query}' in your default browser.")
                    except Exception as os_e:
                        print(f"[WARN] os.startfile failed: {os_e}")
                        print("Sorry, something went wrong while opening the browser.")
                else:
                    print(f"Opened Amazon search for '{query}' in your browser.")
            except Exception as e:
                print(f"[ERROR] Could not open browser: {e}")
                print("Sorry, something went wrong while opening the browser.")
            return None
        
        # If no API key, just open browser
        if not self.api_key:
            self.open_amazon_search(query)
            return None
            
        data = {
            "source": "amazon_search",
            "query": query,
            "geo_location": location,
            "domain": "com",
            "parse": True
        }
        
        result = self._make_request('/queries', data)
        products = []
        
        # Check for the actual structure: results[0].content.results.paid
        if (result and 'results' in result and 
            isinstance(result['results'], list) and 
            len(result['results']) > 0 and
            'content' in result['results'][0] and
            'results' in result['results'][0]['content'] and
            'paid' in result['results'][0]['content']['results']):
            
            products = result['results'][0]['content']['results']['paid'][:limit]
        
        # Fallback to other possible structures
        elif result and 'data' in result and 'search_results' in result['data']:
            products = result['data']['search_results'][:limit]
        elif result and 'data' in result and isinstance(result['data'], list):
            products = result['data'][:limit]
        elif result and 'result' in result and isinstance(result['result'], list):
            products = result['result'][:limit]
        elif result and isinstance(result, list):
            products = result[:limit]
            
        return products if products else None
    
    def get_product_details(self, asin: str, location: str = "90210") -> Optional[Dict]:
        """Get detailed product information"""
        if not self.api_key:
            print("[ERROR] RapidAPI key required for product details")
            return None
            
        data = {
            "source": "amazon_product",
            "query": asin,
            "geo_location": location,
            "parse": True
        }
        result = self._make_request('/queries', data)
        
        if result and 'data' in result and 'product' in result['data']:
            return result['data']['product']
        elif result and 'data' in result:
            return result['data']
        elif result and 'result' in result:
            return result['result']
        return result
    
    def get_product_price(self, asin: str, location: str = "90210") -> Optional[Dict]:
        """Get current product price - using product details endpoint"""
        product_details = self.get_product_details(asin, location)
        if product_details:
            price = product_details.get('price') or product_details.get('current_price')
            currency = product_details.get('currency', 'USD')
            title = product_details.get('title') or product_details.get('name') or 'Unknown Product'
            price_info = {
                'price': price,
                'currency': currency,
                'title': title
            }
            return price_info
        return None
    
    def get_product_reviews(self, asin: str, location: str = "90210", limit: int = 5) -> Optional[List[Dict]]:
        """Get product reviews - using product details endpoint"""
        product_details = self.get_product_details(asin, location)
        if product_details and 'reviews' in product_details:
            return product_details['reviews'][:limit]
        return None
    
    def get_deals(self, category: str = "all", limit: int = 5) -> Optional[List[Dict]]:
        """Get current deals - using search with deal keywords"""
        deal_queries = ["deal", "sale", "discount", "offer"]
        all_deals = []
        
        for query in deal_queries:
            if category != "all":
                search_query = f"{category} {query}"
            else:
                search_query = query
            
            products = self.search_products(search_query, limit=limit//len(deal_queries))
            if products:
                all_deals.extend(products)
        
        return all_deals[:limit] if all_deals else None
    
    def track_price(self, asin: str, location: str = "90210", note: str = "") -> Dict[str, Any]:
        """Track price changes for a product"""
        price_info = self.get_product_price(asin, location)
        if not price_info:
            return {"error": "Could not get price information"}
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO price_tracking (asin, product_title, current_price, currency, user_note)
            VALUES (?, ?, ?, ?, ?)
        ''', (asin, price_info.get('title'), price_info.get('price'), 
              price_info.get('currency', 'USD'), note))
        conn.commit()
        conn.close()
        
        tracking_data = {
            "asin": asin,
            "current_price": price_info.get('price'),
            "currency": price_info.get('currency', 'USD'),
            "timestamp": datetime.now().isoformat(),
            "product_title": price_info.get('title', 'Unknown Product'),
            "note": note
        }
        
        return tracking_data
    
    def get_tracked_products(self) -> List[Dict]:
        """Get all tracked products"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT asin, product_title, current_price, currency, timestamp, user_note
            FROM price_tracking
            ORDER BY timestamp DESC
        ''')
        results = cursor.fetchall()
        conn.close()
        
        tracked_products = []
        for row in results:
            tracked_products.append({
                'asin': row[0],
                'product_title': row[1],
                'current_price': row[2],
                'currency': row[3],
                'timestamp': row[4],
                'note': row[5]
            })
        
        return tracked_products
    
    def remove_tracking(self, asin: str) -> bool:
        """Remove a product from price tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM price_tracking WHERE asin = ?', (asin,))
        affected_rows = cursor.rowcount
        conn.commit()
        conn.close()
        return affected_rows > 0
    
    def compare_prices(self, query: str, location: str = "90210") -> Optional[List[Dict]]:
        """Compare prices across different sellers"""
        products = self.search_products(query, location, limit=3)
        if not products:
            return None
        
        price_comparison = []
        for product in products:
            asin = product.get('asin') or product.get('product_id')
            if asin:
                price_info = self.get_product_price(asin, location)
                if price_info:
                    price_comparison.append({
                        'title': product.get('title', 'Unknown') or product.get('name', 'Unknown'),
                        'price': price_info.get('price'),
                        'currency': price_info.get('currency', 'USD'),
                        'seller': price_info.get('seller', 'Unknown'),
                        'rating': product.get('rating'),
                        'reviews_count': product.get('reviews_count')
                    })
        
        return price_comparison

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for Amazon shopping"""
        cmd = cmd.lower()
        
        if "search" in cmd or "find" in cmd:
            # Extract search query
            query = cmd.replace("search", "").replace("find", "").replace("on amazon", "").strip()
            if query:
                products = self.search_products(query, open_browser=True)
                if products:
                    return f"Found {len(products)} products for '{query}'. Opened results in your browser."
                else:
                    return f"Opened Amazon search for '{query}' in your browser."
            else:
                return "Please specify what you want to search for."
                
        elif "open amazon" in cmd:
            self.open_amazon_search("")
            return "Opened Amazon in your browser."
            
        elif "track price" in cmd or "monitor price" in cmd:
            # Extract ASIN or product name
            parts = cmd.split()
            if "asin" in parts:
                asin_index = parts.index("asin") + 1
                if asin_index < len(parts):
                    asin = parts[asin_index]
                    result = self.track_price(asin)
                    if "error" not in result:
                        return f"Started tracking price for {result['product_title']}"
                    else:
                        return "Could not track price. Please check the ASIN."
            else:
                return "Please specify the ASIN to track. Say 'track price ASIN B08N5WRWNW'"
                
        elif "show tracked" in cmd or "tracked products" in cmd:
            tracked = self.get_tracked_products()
            if tracked:
                return f"You have {len(tracked)} tracked products. Check the app for details."
            else:
                return "You have no tracked products."
                
        elif "deals" in cmd or "sales" in cmd:
            category = "all"
            if "electronics" in cmd:
                category = "electronics"
            elif "books" in cmd:
                category = "books"
            elif "clothing" in cmd:
                category = "clothing"
                
            deals = self.get_deals(category, limit=3)
            if deals:
                return f"Found {len(deals)} deals in {category}. Check your browser for details."
            else:
                return f"No deals found in {category}."
        else:
            return "Amazon command not recognized. Try 'search [product]', 'open amazon', 'track price ASIN [number]', or 'show deals'."

# Voice command helper functions
def format_product_info(product: Dict) -> str:
    """Format product information for voice output"""
    title = product.get('title', 'Unknown Product')
    price = product.get('price', 'Price not available')
    rating = product.get('rating', 'No rating')
    reviews = product.get('reviews_count', 0)
    
    return f"{title} - Price: {price}, Rating: {rating} stars with {reviews} reviews"

def format_deal_info(deal: Dict) -> str:
    """Format deal information for voice output"""
    title = deal.get('title', 'Unknown Deal')
    original_price = deal.get('original_price', 'Unknown')
    current_price = deal.get('current_price', 'Unknown')
    discount = deal.get('discount_percentage', 0)
    
    return f"{title} - Original: {original_price}, Now: {current_price}, {discount}% off"

def format_review_info(review: Dict) -> str:
    """Format review information for voice output"""
    rating = review.get('rating', 0)
    title = review.get('title', 'No title')
    content = review.get('content', 'No content')[:100] + "..." if len(review.get('content', '')) > 100 else review.get('content', 'No content')
    
    return f"{rating} stars - {title}: {content}" 