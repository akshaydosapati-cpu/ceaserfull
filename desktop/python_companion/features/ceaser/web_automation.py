import time
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import threading
import sqlite3
from pathlib import Path
import webbrowser
import urllib.parse

# Try to import Selenium for advanced web automation
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("[INFO] Selenium not available. Using basic web automation.")

class WebAutomationAssistant:
    def __init__(self, db_path='web_automation.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Web driver instance
        self.driver = None
        self.driver_lock = threading.Lock()
        
        # Automation templates and macros
        self.automation_templates = {}
        self.active_macros = {}
        
        # Common website configurations
        self.website_configs = {
            'google': {
                'search_box': 'q',
                'search_button': 'btnK',
                'results_container': 'search'
            },
            'youtube': {
                'search_box': 'search_query',
                'search_button': 'search-btn',
                'video_links': 'ytd-video-renderer'
            },
            'github': {
                'search_box': 'q',
                'search_button': 'jump-to-suggestion-search-no-global-typeahead',
                'repo_links': 'repo-list-item'
            }
        }

    def _create_tables(self):
        """Create SQLite tables for web automation"""
        with self.conn:
            # Automation scripts
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS automation_scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    script_data TEXT,
                    website TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used DATETIME,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0
                )
            ''')
            
            # Automation history
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS automation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script_id INTEGER,
                    script_name TEXT,
                    status TEXT,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    end_time DATETIME,
                    error_message TEXT,
                    FOREIGN KEY (script_id) REFERENCES automation_scripts (id)
                )
            ''')
            
            # Website credentials (encrypted)
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS website_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website TEXT NOT NULL,
                    username TEXT,
                    encrypted_password TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used DATETIME
                )
            ''')
            
            # Create indexes
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_scripts_name ON automation_scripts(name)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_history_script ON automation_history(script_id)')

    def initialize_driver(self, headless: bool = False) -> bool:
        """Initialize the web driver"""
        if not SELENIUM_AVAILABLE:
            self.logger.warning("Selenium not available for advanced automation")
            return False
        
        try:
            with self.driver_lock:
                if self.driver:
                    self.driver.quit()
                
                chrome_options = Options()
                if headless:
                    chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920,1080")
                
                # Try to find Chrome driver
                try:
                    self.driver = webdriver.Chrome(options=chrome_options)
                except Exception as e:
                    self.logger.error(f"Failed to initialize Chrome driver: {e}")
                    return False
                
                self.driver.implicitly_wait(10)
                self.logger.info("Web driver initialized successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to initialize web driver: {e}")
            return False

    def navigate_to_url(self, url: str) -> bool:
        """Navigate to a specific URL"""
        try:
            if self.driver:
                with self.driver_lock:
                    self.driver.get(url)
                    self.logger.info(f"Navigated to: {url}")
                    return True
            else:
                # Fallback to default browser
                webbrowser.open(url)
                self.logger.info(f"Opened in default browser: {url}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to navigate to {url}: {e}")
            return False

    def search_google(self, query: str) -> bool:
        """Perform a Google search"""
        try:
            if not self.driver:
                # Fallback to direct URL
                search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                return self.navigate_to_url(search_url)
            
            with self.driver_lock:
                self.driver.get("https://www.google.com")
                
                # Find and fill search box
                search_box = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "q"))
                )
                search_box.clear()
                search_box.send_keys(query)
                search_box.send_keys(Keys.RETURN)
                
                self.logger.info(f"Performed Google search for: {query}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to perform Google search: {e}")
            return False

    def fill_form(self, form_data: Dict[str, str], form_selectors: Dict[str, str]) -> bool:
        """Fill out a web form"""
        try:
            if not self.driver:
                self.logger.error("No web driver available for form filling")
                return False
            
            with self.driver_lock:
                for field_name, value in form_data.items():
                    if field_name in form_selectors:
                        selector = form_selectors[field_name]
                        try:
                            # Try different selector strategies
                            element = None
                            if selector.startswith('#'):
                                element = self.driver.find_element(By.ID, selector[1:])
                            elif selector.startswith('.'):
                                element = self.driver.find_element(By.CLASS_NAME, selector[1:])
                            elif selector.startswith('name='):
                                element = self.driver.find_element(By.NAME, selector[5:])
                            else:
                                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                            
                            if element:
                                element.clear()
                                element.send_keys(value)
                                self.logger.info(f"Filled field {field_name}: {value}")
                                
                        except NoSuchElementException:
                            self.logger.warning(f"Could not find form field: {field_name}")
                            continue
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to fill form: {e}")
            return False

    def click_element(self, selector: str, selector_type: str = "css") -> bool:
        """Click on a web element"""
        try:
            if not self.driver:
                self.logger.error("No web driver available for clicking")
                return False
            
            with self.driver_lock:
                if selector_type == "id":
                    element = self.driver.find_element(By.ID, selector)
                elif selector_type == "class":
                    element = self.driver.find_element(By.CLASS_NAME, selector)
                elif selector_type == "name":
                    element = self.driver.find_element(By.NAME, selector)
                elif selector_type == "xpath":
                    element = self.driver.find_element(By.XPATH, selector)
                else:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                element.click()
                self.logger.info(f"Clicked element: {selector}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to click element {selector}: {e}")
            return False

    def extract_text(self, selector: str, selector_type: str = "css") -> Optional[str]:
        """Extract text from a web element"""
        try:
            if not self.driver:
                self.logger.error("No web driver available for text extraction")
                return None
            
            with self.driver_lock:
                if selector_type == "id":
                    element = self.driver.find_element(By.ID, selector)
                elif selector_type == "class":
                    element = self.driver.find_element(By.CLASS_NAME, selector)
                elif selector_type == "name":
                    element = self.driver.find_element(By.NAME, selector)
                elif selector_type == "xpath":
                    element = self.driver.find_element(By.XPATH, selector)
                else:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                text = element.text
                self.logger.info(f"Extracted text from {selector}: {text[:50]}...")
                return text
                
        except Exception as e:
            self.logger.error(f"Failed to extract text from {selector}: {e}")
            return None

    def wait_for_element(self, selector: str, timeout: int = 10, selector_type: str = "css") -> bool:
        """Wait for an element to appear on the page"""
        try:
            if not self.driver:
                return False
            
            with self.driver_lock:
                wait = WebDriverWait(self.driver, timeout)
                
                if selector_type == "id":
                    wait.until(EC.presence_of_element_located((By.ID, selector)))
                elif selector_type == "class":
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, selector)))
                elif selector_type == "name":
                    wait.until(EC.presence_of_element_located((By.NAME, selector)))
                elif selector_type == "xpath":
                    wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                else:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                
                return True
                
        except TimeoutException:
            self.logger.warning(f"Element {selector} not found within {timeout} seconds")
            return False
        except Exception as e:
            self.logger.error(f"Failed to wait for element {selector}: {e}")
            return False

    def save_automation_script(self, name: str, description: str, script_data: Dict[str, Any], 
                             website: str = "") -> int:
        """Save an automation script"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO automation_scripts (name, description, script_data, website)
                    VALUES (?, ?, ?, ?)
                ''', (name, description, json.dumps(script_data), website))
                
                script_id = cursor.lastrowid
                self.logger.info(f"Saved automation script: {name} (ID: {script_id})")
                return script_id
                
        except Exception as e:
            self.logger.error(f"Failed to save automation script: {e}")
            return -1

    def get_automation_scripts(self, website: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get saved automation scripts"""
        try:
            cursor = self.conn.cursor()
            if website:
                cursor.execute('''
                    SELECT id, name, description, script_data, website, created_at, 
                           last_used, success_count, failure_count
                    FROM automation_scripts
                    WHERE website = ?
                    ORDER BY name
                ''', (website,))
            else:
                cursor.execute('''
                    SELECT id, name, description, script_data, website, created_at, 
                           last_used, success_count, failure_count
                    FROM automation_scripts
                    ORDER BY name
                ''')
            
            scripts = []
            for row in cursor.fetchall():
                script_id, name, description, script_data, website, created_at, last_used, success_count, failure_count = row
                scripts.append({
                    'id': script_id,
                    'name': name,
                    'description': description,
                    'script_data': json.loads(script_data),
                    'website': website,
                    'created_at': created_at,
                    'last_used': last_used,
                    'success_count': success_count,
                    'failure_count': failure_count
                })
            
            return scripts
            
        except Exception as e:
            self.logger.error(f"Failed to get automation scripts: {e}")
            return []

    def run_automation_script(self, script_id: int) -> bool:
        """Run a saved automation script"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT name, script_data FROM automation_scripts WHERE id = ?
            ''', (script_id,))
            
            result = cursor.fetchone()
            if not result:
                self.logger.error(f"Script {script_id} not found")
                return False
            
            script_name, script_data = result
            script_steps = json.loads(script_data)
            
            # Record start time
            start_time = datetime.now()
            
            try:
                # Execute script steps
                for step in script_steps:
                    step_type = step.get('type')
                    
                    if step_type == 'navigate':
                        self.navigate_to_url(step['url'])
                    elif step_type == 'click':
                        self.click_element(step['selector'], step.get('selector_type', 'css'))
                    elif step_type == 'fill':
                        self.fill_form(step['form_data'], step['selectors'])
                    elif step_type == 'wait':
                        time.sleep(step.get('duration', 1))
                    elif step_type == 'wait_for_element':
                        self.wait_for_element(step['selector'], step.get('timeout', 10))
                    elif step_type == 'extract':
                        text = self.extract_text(step['selector'], step.get('selector_type', 'css'))
                        if text:
                            step['result'] = text
                
                # Record success
                end_time = datetime.now()
                with self.conn:
                    self.conn.execute('''
                        UPDATE automation_scripts 
                        SET last_used = CURRENT_TIMESTAMP, success_count = success_count + 1
                        WHERE id = ?
                    ''', (script_id,))
                    
                    self.conn.execute('''
                        INSERT INTO automation_history (script_id, script_name, status, start_time, end_time)
                        VALUES (?, ?, 'success', ?, ?)
                    ''', (script_id, script_name, start_time, end_time))
                
                self.logger.info(f"Successfully ran automation script: {script_name}")
                return True
                
            except Exception as e:
                # Record failure
                end_time = datetime.now()
                with self.conn:
                    self.conn.execute('''
                        UPDATE automation_scripts 
                        SET last_used = CURRENT_TIMESTAMP, failure_count = failure_count + 1
                        WHERE id = ?
                    ''', (script_id,))
                    
                    self.conn.execute('''
                        INSERT INTO automation_history (script_id, script_name, status, start_time, end_time, error_message)
                        VALUES (?, ?, 'failed', ?, ?, ?)
                    ''', (script_id, script_name, start_time, end_time, str(e)))
                
                self.logger.error(f"Failed to run automation script {script_name}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to run automation script: {e}")
            return False

    def book_meeting(self, meeting_data: Dict[str, str]) -> bool:
        """Automate meeting booking (template for common platforms)"""
        try:
            # This is a template - would need to be customized for specific platforms
            script_data = {
                'steps': [
                    {'type': 'navigate', 'url': meeting_data.get('platform_url', 'https://calendar.google.com')},
                    {'type': 'wait', 'duration': 2},
                    {'type': 'click', 'selector': meeting_data.get('new_event_selector', '[data-testid="create-event-button"]')},
                    {'type': 'wait_for_element', 'selector': meeting_data.get('title_selector', 'input[name="title"]')},
                    {'type': 'fill', 'form_data': {
                        'title': meeting_data.get('title', ''),
                        'description': meeting_data.get('description', ''),
                        'date': meeting_data.get('date', ''),
                        'time': meeting_data.get('time', '')
                    }, 'selectors': {
                        'title': meeting_data.get('title_selector', 'input[name="title"]'),
                        'description': meeting_data.get('description_selector', 'textarea[name="description"]'),
                        'date': meeting_data.get('date_selector', 'input[name="date"]'),
                        'time': meeting_data.get('time_selector', 'input[name="time"]')
                    }},
                    {'type': 'click', 'selector': meeting_data.get('save_selector', 'button[type="submit"]')}
                ]
            }
            
            # Save as automation script
            script_id = self.save_automation_script(
                f"Meeting Booking - {meeting_data.get('title', 'Untitled')}",
                "Automated meeting booking script",
                script_data,
                meeting_data.get('platform', 'calendar')
            )
            
            if script_id > 0:
                return self.run_automation_script(script_id)
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to book meeting: {e}")
            return False

    def fill_online_form(self, form_data: Dict[str, str], form_url: str, 
                        form_selectors: Dict[str, str]) -> bool:
        """Fill out an online form"""
        try:
            script_data = {
                'steps': [
                    {'type': 'navigate', 'url': form_url},
                    {'type': 'wait_for_element', 'selector': list(form_selectors.values())[0]},
                    {'type': 'fill', 'form_data': form_data, 'selectors': form_selectors},
                    {'type': 'click', 'selector': form_selectors.get('submit_button', 'button[type="submit"]')}
                ]
            }
            
            # Save as automation script
            script_id = self.save_automation_script(
                f"Form Fill - {form_url}",
                "Automated form filling script",
                script_data,
                form_url
            )
            
            if script_id > 0:
                return self.run_automation_script(script_id)
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to fill online form: {e}")
            return False

    def get_automation_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get automation execution history"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT script_name, status, start_time, end_time, error_message
                FROM automation_history
                ORDER BY start_time DESC
                LIMIT ?
            ''', (limit,))
            
            history = []
            for row in cursor.fetchall():
                script_name, status, start_time, end_time, error_message = row
                history.append({
                    'script_name': script_name,
                    'status': status,
                    'start_time': start_time,
                    'end_time': end_time,
                    'error_message': error_message
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Failed to get automation history: {e}")
            return []

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for web automation"""
        cmd = cmd.lower()
        
        if "search google" in cmd or "google search" in cmd:
            # Extract search query
            query_start = cmd.find("for") + 4 if "for" in cmd else cmd.find("search") + 7
            query = cmd[query_start:].strip()
            if query:
                if self.search_google(query):
                    return f"Performed Google search for: {query}"
                else:
                    return "Failed to perform Google search. Please try again."
            else:
                return "Please specify what to search for. Say 'search google for [query]'"
        
        elif "open website" in cmd or "go to" in cmd:
            # Extract URL
            url_start = cmd.find("website") + 8 if "website" in cmd else cmd.find("to") + 3
            url = cmd[url_start:].strip()
            if url:
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                if self.navigate_to_url(url):
                    return f"Opened website: {url}"
                else:
                    return "Failed to open website. Please try again."
            else:
                return "Please specify the website. Say 'open website [url]'"
        
        elif "book meeting" in cmd:
            # This would need more context gathering
            return "To book a meeting, I need more details. Please specify the platform, title, date, and time."
        
        elif "automation scripts" in cmd or "saved scripts" in cmd:
            scripts = self.get_automation_scripts()
            if scripts:
                return f"You have {len(scripts)} saved automation scripts. Check the app for details."
            else:
                return "You have no saved automation scripts."
        
        elif "automation history" in cmd:
            history = self.get_automation_history(limit=5)
            if history:
                return f"You have {len(history)} recent automation executions. Check the app for details."
            else:
                return "No automation history available."
        
        else:
            return "Web automation command not recognized. Try 'search google for [query]', 'open website [url]', or 'automation scripts'."

    def close_driver(self):
        """Close the web driver"""
        try:
            with self.driver_lock:
                if self.driver:
                    self.driver.quit()
                    self.driver = None
                    self.logger.info("Web driver closed")
        except Exception as e:
            self.logger.error(f"Failed to close web driver: {e}")

    def close(self):
        """Close database connection and web driver"""
        self.close_driver()
        if self.conn:
            self.conn.close()

# Voice command helper functions
def format_script_info(script: Dict[str, Any]) -> str:
    """Format script information for voice output"""
    name = script.get('name', 'Untitled')
    website = script.get('website', 'general')
    success_count = script.get('success_count', 0)
    failure_count = script.get('failure_count', 0)
    
    return f"Script '{name}' for {website}, {success_count} successful runs, {failure_count} failures"

def format_history_info(history: Dict[str, Any]) -> str:
    """Format history information for voice output"""
    script_name = history.get('script_name', 'Unknown')
    status = history.get('status', 'unknown')
    start_time = history.get('start_time', 'Unknown')
    
    return f"Script '{script_name}' {status} at {start_time}" 