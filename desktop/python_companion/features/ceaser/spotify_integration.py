import requests
import base64
import json
import time
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv
import subprocess
import ctypes

# Load environment variables, but don't fail if .env doesn't exist
try:
    load_dotenv()
except Exception as e:
    print(f"[INFO] Could not load .env file: {e}")

class SpotifyIntegration:
    def __init__(self):
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0
        
        # Try to load saved tokens
        self._load_saved_tokens()
        
        # Spotify API endpoints
        self.auth_url = "https://accounts.spotify.com/authorize"
        self.token_url = "https://accounts.spotify.com/api/token"
        self.api_base = "https://api.spotify.com/v1"
        
        # Scopes needed for full functionality
        self.scopes = [
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
            "playlist-read-private",
            "playlist-modify-public",
            "playlist-modify-private",
            "user-library-read",
            "user-library-modify",
            "user-read-recently-played",
            "user-top-read"
        ]
        
        self.scope_string = " ".join(self.scopes)
    
    def _load_saved_tokens(self):
        """Load saved tokens from file"""
        try:
            import json
            with open('spotify_tokens.json', 'r') as f:
                tokens = json.load(f)
            
            self.access_token = tokens.get('access_token')
            self.refresh_token = tokens.get('refresh_token')
            self.token_expiry = tokens.get('token_expiry', 0)
            
            print("[INFO] Loaded saved Spotify tokens")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            print("[INFO] No saved Spotify tokens found")
    
    def get_auth_url(self) -> str:
        """Generate authorization URL for user to visit"""
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': 'https://oauth.pstmn.io/v1/callback',
            'scope': self.scope_string,
            'show_dialog': 'true'
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"
    
    def get_access_token(self, auth_code: str) -> bool:
        """Exchange authorization code for access token"""
        if not self.client_id or not self.client_secret:
            print("[ERROR] Spotify credentials not found. Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env file")
            return False
        
        # Encode credentials
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': 'https://oauth.pstmn.io/v1/callback'
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')
            self.token_expiry = time.time() + token_data['expires_in']
            
            print("[SUCCESS] Spotify authentication successful!")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to get access token: {e}")
            return False
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            print("[ERROR] No refresh token available")
            return False
        
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.token_expiry = time.time() + token_data['expires_in']
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to refresh token: {e}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with current access token"""
        if not self.access_token or time.time() >= self.token_expiry:
            if not self.refresh_access_token():
                return {}
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to Spotify API"""
        headers = self._get_headers()
        if not headers:
            return None
        
        url = f"{self.api_base}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers)
            
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Spotify API request failed: {e}")
            return None
    
    # Playback Control Methods
    def get_current_playback(self) -> Optional[Dict]:
        """Get current playback state"""
        return self._make_request('GET', '/me/player')
    
    def start_playback(self, uris: Optional[List[str]] = None, context_uri: Optional[str] = None) -> bool:
        """Start or resume playback"""
        data = {}
        if uris:
            data['uris'] = uris
        if context_uri:
            data['context_uri'] = context_uri
        
        result = self._make_request('PUT', '/me/player/play', data if data else None)
        return result is not None
    
    def pause_playback(self) -> bool:
        """Pause playback"""
        result = self._make_request('PUT', '/me/player/pause')
        return result is not None
    
    def skip_to_next(self) -> bool:
        """Skip to next track"""
        result = self._make_request('POST', '/me/player/next')
        return result is not None
    
    def skip_to_previous(self) -> bool:
        """Skip to previous track"""
        result = self._make_request('POST', '/me/player/previous')
        return result is not None
    
    def set_volume(self, volume_percent: int) -> bool:
        """Set playback volume (0-100)"""
        if not 0 <= volume_percent <= 100:
            return False
        
        result = self._make_request('PUT', f'/me/player/volume?volume_percent={volume_percent}')
        return result is not None
    
    # Search Methods
    def search_tracks(self, query: str, limit: int = 5) -> Optional[List[Dict]]:
        """Search for tracks"""
        params = f"?q={query}&type=track&limit={limit}"
        result = self._make_request('GET', f'/search{params}')
        
        if result and 'tracks' in result:
            return result['tracks']['items']
        return None
    
    def search_artists(self, query: str, limit: int = 5) -> Optional[List[Dict]]:
        """Search for artists"""
        params = f"?q={query}&type=artist&limit={limit}"
        result = self._make_request('GET', f'/search{params}')
        
        if result and 'artists' in result:
            return result['artists']['items']
        return None
    
    def search_playlists(self, query: str, limit: int = 5) -> Optional[List[Dict]]:
        """Search for playlists"""
        params = f"?q={query}&type=playlist&limit={limit}"
        result = self._make_request('GET', f'/search{params}')
        
        if result and 'playlists' in result:
            return result['playlists']['items']
        return None
    
    # Playlist Methods
    def get_user_playlists(self, limit: int = 20) -> Optional[List[Dict]]:
        """Get user's playlists"""
        result = self._make_request('GET', f'/me/playlists?limit={limit}')
        
        if result and 'items' in result:
            return result['items']
        return None
    
    def get_playlist_tracks(self, playlist_id: str, limit: int = 50) -> Optional[List[Dict]]:
        """Get tracks from a playlist"""
        result = self._make_request('GET', f'/playlists/{playlist_id}/tracks?limit={limit}')
        
        if result and 'items' in result:
            return [item['track'] for item in result['items'] if item['track']]
        return None
    
    def create_playlist(self, name: str, description: str = "", public: bool = False) -> Optional[str]:
        """Create a new playlist"""
        # First get user ID
        user_result = self._make_request('GET', '/me')
        if not user_result or 'id' not in user_result:
            return None
        
        user_id = user_result['id']
        
        data = {
            'name': name,
            'description': description,
            'public': public
        }
        
        result = self._make_request('POST', f'/users/{user_id}/playlists', data)
        
        if result and 'id' in result:
            return result['id']
        return None
    
    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Add tracks to a playlist"""
        data = {'uris': track_uris}
        result = self._make_request('POST', f'/playlists/{playlist_id}/tracks', data)
        return result is not None
    
    # Library Methods
    def get_saved_tracks(self, limit: int = 20) -> Optional[List[Dict]]:
        """Get user's saved tracks"""
        result = self._make_request('GET', f'/me/tracks?limit={limit}')
        
        if result and 'items' in result:
            return [item['track'] for item in result['items'] if item['track']]
        return None
    
    def save_track(self, track_id: str) -> bool:
        """Save a track to user's library"""
        result = self._make_request('PUT', f'/me/tracks?ids={track_id}')
        return result is not None
    
    def remove_saved_track(self, track_id: str) -> bool:
        """Remove a track from user's library"""
        result = self._make_request('DELETE', f'/me/tracks?ids={track_id}')
        return result is not None
    
    # Recommendations
    def get_recommendations(self, seed_tracks: Optional[List[str]] = None, 
                          seed_artists: Optional[List[str]] = None,
                          seed_genres: Optional[List[str]] = None,
                          limit: int = 20) -> Optional[List[Dict]]:
        """Get track recommendations"""
        params = f"?limit={limit}"
        
        if seed_tracks:
            params += f"&seed_tracks={','.join(seed_tracks[:5])}"
        if seed_artists:
            params += f"&seed_artists={','.join(seed_artists[:5])}"
        if seed_genres:
            params += f"&seed_genres={','.join(seed_genres[:5])}"
        
        result = self._make_request('GET', f'/recommendations{params}')
        
        if result and 'tracks' in result:
            return result['tracks']
        return None
    
    # Utility Methods
    def get_track_info(self, track_id: str) -> Optional[Dict]:
        """Get detailed track information"""
        return self._make_request('GET', f'/tracks/{track_id}')
    
    def get_artist_info(self, artist_id: str) -> Optional[Dict]:
        """Get detailed artist information"""
        return self._make_request('GET', f'/artists/{artist_id}')
    
    def get_album_info(self, album_id: str) -> Optional[Dict]:
        """Get detailed album information"""
        return self._make_request('GET', f'/albums/{album_id}')
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.access_token is not None and time.time() < self.token_expiry
    
    def get_auth_status(self) -> str:
        """Get authentication status message"""
        if not self.client_id or not self.client_secret:
            return "Spotify credentials not configured"
        elif not self.is_authenticated():
            return "Not authenticated - need to authorize"
        else:
            return "Authenticated and ready to use"

# Voice command helper methods
def format_track_info(track: Dict) -> str:
    """Format track information for voice output"""
    name = track.get('name', 'Unknown')
    artists = [artist['name'] for artist in track.get('artists', [])]
    artist_names = ', '.join(artists) if artists else 'Unknown Artist'
    album = track.get('album', {}).get('name', 'Unknown Album')
    
    return f"{name} by {artist_names} from {album}"

def format_playlist_info(playlist: Dict) -> str:
    """Format playlist information for voice output"""
    name = playlist.get('name', 'Unknown')
    track_count = playlist.get('tracks', {}).get('total', 0)
    owner = playlist.get('owner', {}).get('display_name', 'Unknown')
    
    return f"{name} by {owner} with {track_count} tracks" 

class MediaControl:
    @staticmethod
    def play_pause():
        """Toggle play/pause using media key."""
        try:
            VK_MEDIA_PLAY_PAUSE = 0xB3
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)
            return "Play/Pause toggled."
        except Exception as e:
            return f"Failed to toggle play/pause: {e}"

    @staticmethod
    def next_track():
        try:
            VK_MEDIA_NEXT_TRACK = 0xB0
            ctypes.windll.user32.keybd_event(VK_MEDIA_NEXT_TRACK, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_MEDIA_NEXT_TRACK, 0, 2, 0)
            return "Next track triggered."
        except Exception as e:
            return f"Failed to go to next track: {e}"

    @staticmethod
    def prev_track():
        try:
            VK_MEDIA_PREV_TRACK = 0xB1
            ctypes.windll.user32.keybd_event(VK_MEDIA_PREV_TRACK, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_MEDIA_PREV_TRACK, 0, 2, 0)
            return "Previous track triggered."
        except Exception as e:
            return f"Failed to go to previous track: {e}"

    @staticmethod
    def stop():
        try:
            VK_MEDIA_STOP = 0xB2
            ctypes.windll.user32.keybd_event(VK_MEDIA_STOP, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_MEDIA_STOP, 0, 2, 0)
            return "Stop triggered."
        except Exception as e:
            return f"Failed to stop: {e}" 