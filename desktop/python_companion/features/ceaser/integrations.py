import requests
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

class IntegrationsAssistant:
    def __init__(self):
        self.integrations = {}
        self.api_keys = {}
        self.logger = logging.getLogger(__name__)
        
        # Load API keys from environment
        self._load_api_keys()
        
        # Initialize available integrations
        self._init_integrations()
    
    def _load_api_keys(self):
        """Load API keys from environment variables"""
        self.api_keys = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'spotify_client_id': os.getenv('SPOTIFY_CLIENT_ID'),
            'spotify_client_secret': os.getenv('SPOTIFY_CLIENT_SECRET'),
            'weather': os.getenv('OPENWEATHER_API_KEY') or os.getenv('WEATHER_API_KEY'),
            'news': os.getenv('NEWS_API_KEY') or os.getenv('GNEWS_API_KEY'),
            'rapidapi': os.getenv('RAPIDAPI_KEY'),
            'google_calendar': os.getenv('GOOGLE_CALENDAR_API_KEY'),
            'slack': os.getenv('SLACK_BOT_TOKEN'),
            'discord': os.getenv('DISCORD_BOT_TOKEN'),
            'telegram': os.getenv('TELEGRAM_BOT_TOKEN'),
            'github': os.getenv('GITHUB_TOKEN'),
            'jira': os.getenv('JIRA_API_TOKEN'),
            'notion': os.getenv('NOTION_API_KEY'),
            'trello': os.getenv('TRELLO_API_KEY'),
            'asana': os.getenv('ASANA_API_KEY'),
            'zoom': os.getenv('ZOOM_API_KEY'),
            'teams': os.getenv('TEAMS_WEBHOOK_URL'),
            'email': os.getenv('EMAIL_PASSWORD'),
        }
    
    def _init_integrations(self):
        """Initialize available integrations"""
        self.integrations = {
            'weather': {
                'name': 'Weather Service',
                'status': 'available' if self.api_keys.get('weather') else 'no_api_key',
                'description': 'Get weather information for any location'
            },
            'news': {
                'name': 'News Service',
                'status': 'available' if self.api_keys.get('news') else 'no_api_key',
                'description': 'Get latest news and headlines'
            },
            'spotify': {
                'name': 'Spotify Music',
                'status': 'available' if self.api_keys.get('spotify_client_id') else 'no_api_key',
                'description': 'Control Spotify music playback'
            },
            'calendar': {
                'name': 'Google Calendar',
                'status': 'available' if self.api_keys.get('google_calendar') else 'no_api_key',
                'description': 'Manage calendar events and schedules'
            },
            'slack': {
                'name': 'Slack',
                'status': 'available' if self.api_keys.get('slack') else 'no_api_key',
                'description': 'Send messages and manage Slack workspace'
            },
            'discord': {
                'name': 'Discord',
                'status': 'available' if self.api_keys.get('discord') else 'no_api_key',
                'description': 'Send messages and manage Discord server'
            },
            'telegram': {
                'name': 'Telegram',
                'status': 'available' if self.api_keys.get('telegram') else 'no_api_key',
                'description': 'Send messages and manage Telegram bot'
            },
            'github': {
                'name': 'GitHub',
                'status': 'available' if self.api_keys.get('github') else 'no_api_key',
                'description': 'Manage GitHub repositories and issues'
            },
            'jira': {
                'name': 'Jira',
                'status': 'available' if self.api_keys.get('jira') else 'no_api_key',
                'description': 'Manage Jira projects and tickets'
            },
            'notion': {
                'name': 'Notion',
                'status': 'available' if self.api_keys.get('notion') else 'no_api_key',
                'description': 'Manage Notion databases and pages'
            },
            'trello': {
                'name': 'Trello',
                'status': 'available' if self.api_keys.get('trello') else 'no_api_key',
                'description': 'Manage Trello boards and cards'
            },
            'asana': {
                'name': 'Asana',
                'status': 'available' if self.api_keys.get('asana') else 'no_api_key',
                'description': 'Manage Asana projects and tasks'
            },
            'zoom': {
                'name': 'Zoom',
                'status': 'available' if self.api_keys.get('zoom') else 'no_api_key',
                'description': 'Schedule and manage Zoom meetings'
            },
            'teams': {
                'name': 'Microsoft Teams',
                'status': 'available' if self.api_keys.get('teams') else 'no_api_key',
                'description': 'Send messages to Teams channels'
            },
            'email': {
                'name': 'Email Service',
                'status': 'available' if self.api_keys.get('email') else 'no_api_key',
                'description': 'Send emails and manage inbox'
            }
        }
    
    def get_available_integrations(self) -> List[Dict[str, Any]]:
        """Get list of available integrations"""
        return [
            {
                'service': service,
                'name': info['name'],
                'status': info['status'],
                'description': info['description']
            }
            for service, info in self.integrations.items()
        ]
    
    def test_integration(self, service: str) -> Dict[str, Any]:
        """Test if an integration is working"""
        if service not in self.integrations:
            return {'success': False, 'error': f'Unknown service: {service}'}
        
        if self.integrations[service]['status'] != 'available':
            return {'success': False, 'error': f'Service not available: {self.integrations[service]["status"]}'}
        
        try:
            if service == 'weather':
                return self._test_weather()
            elif service == 'news':
                return self._test_news()
            elif service == 'spotify':
                return self._test_spotify()
            else:
                return {'success': True, 'message': f'{service} integration is available'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_weather(self) -> Dict[str, Any]:
        """Test weather integration"""
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q=London&appid={self.api_keys['weather']}&units=metric"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return {'success': True, 'message': 'Weather API is working'}
            else:
                return {'success': False, 'error': f'Weather API error: {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': f'Weather API test failed: {e}'}
    
    def _test_news(self) -> Dict[str, Any]:
        """Test news integration"""
        try:
            url = f"https://gnews.io/api/v4/top-headlines?lang=en&country=us&max=1&apikey={self.api_keys['news']}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return {'success': True, 'message': 'News API is working'}
            else:
                return {'success': False, 'error': f'News API error: {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': f'News API test failed: {e}'}
    
    def _test_spotify(self) -> Dict[str, Any]:
        """Test Spotify integration"""
        try:
            # Basic test - check if credentials are available
            if self.api_keys.get('spotify_client_id') and self.api_keys.get('spotify_client_secret'):
                return {'success': True, 'message': 'Spotify credentials are configured'}
            else:
                return {'success': False, 'error': 'Spotify credentials not found'}
        except Exception as e:
            return {'success': False, 'error': f'Spotify test failed: {e}'}
    
    def add_integration(self, service: str, api_key: str) -> Dict[str, Any]:
        """Add a new integration"""
        if service not in self.integrations:
            return {'success': False, 'error': f'Unknown service: {service}'}
        
        try:
            # Store the API key (in production, this should be encrypted)
            self.api_keys[service] = api_key
            self.integrations[service]['status'] = 'available'
            
            # Test the integration
            test_result = self.test_integration(service)
            if test_result['success']:
                return {'success': True, 'message': f'{service} integration added successfully'}
            else:
                return {'success': False, 'error': f'Integration added but test failed: {test_result["error"]}'}
        except Exception as e:
            return {'success': False, 'error': f'Failed to add integration: {e}'}
    
    def remove_integration(self, service: str) -> Dict[str, Any]:
        """Remove an integration"""
        if service not in self.integrations:
            return {'success': False, 'error': f'Unknown service: {service}'}
        
        try:
            self.api_keys[service] = None
            self.integrations[service]['status'] = 'no_api_key'
            return {'success': True, 'message': f'{service} integration removed'}
        except Exception as e:
            return {'success': False, 'error': f'Failed to remove integration: {e}'}
    
    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for integrations"""
        cmd_lower = cmd.lower().strip()
        
        if 'list' in cmd_lower or 'show' in cmd_lower:
            integrations = self.get_available_integrations()
            available = [i for i in integrations if i['status'] == 'available']
            unavailable = [i for i in integrations if i['status'] == 'no_api_key']
            
            result = f"Available integrations ({len(available)}): "
            if available:
                result += ", ".join([i['name'] for i in available])
            else:
                result += "None"
            
            result += f"\nUnavailable integrations ({len(unavailable)}): "
            if unavailable:
                result += ", ".join([i['name'] for i in unavailable])
            else:
                result += "None"
            
            return result
        
        elif 'test' in cmd_lower:
            # Extract service name from command
            for service in self.integrations.keys():
                if service in cmd_lower:
                    result = self.test_integration(service)
                    if result['success']:
                        return f"{service} integration test passed: {result['message']}"
                    else:
                        return f"{service} integration test failed: {result['error']}"
            return "Please specify which integration to test"
        
        elif 'add' in cmd_lower:
            # Extract service name from command
            for service in self.integrations.keys():
                if service in cmd_lower:
                    return f"To add {service} integration, please provide the API key"
            return "Please specify which integration to add"
        
        elif 'remove' in cmd_lower or 'delete' in cmd_lower:
            # Extract service name from command
            for service in self.integrations.keys():
                if service in cmd_lower:
                    result = self.remove_integration(service)
                    if result['success']:
                        return f"{service} integration removed"
                    else:
                        return f"Failed to remove {service}: {result['error']}"
            return "Please specify which integration to remove"
        
        else:
            return "Available commands: list integrations, test [service], add [service], remove [service]" 
