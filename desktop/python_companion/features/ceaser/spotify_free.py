#!/usr/bin/env python3
"""
Spotify Free Integration
Opens Spotify links for users without premium accounts
"""

import webbrowser
import requests
from typing import Optional, List, Dict
import urllib.parse

class SpotifyFree:
    def __init__(self):
        self.client_id = "620514a380c940db8591287fd1aef0a9"
        self.client_secret = "3febd1e9d3ae4fb0a9b2a70eaa4c0b38"
        
    def search_and_open(self, query: str) -> str:
        """Search for music on Spotify and open the web player"""
        try:
            # Format the search query for Spotify web player
            search_query = urllib.parse.quote(query)
            url = f"https://open.spotify.com/search/{search_query}"
            
            # Open Spotify web player with search results
            webbrowser.open(url)
            
            return f"Searching for '{query}' on Spotify. The web player should open in your browser. Click play to start listening!"
        except Exception as e:
            return f"Error opening Spotify: {str(e)}"
    
    def open_track(self, track_name: str, artist_name: str = "") -> str:
        """Open a specific track on Spotify"""
        try:
            # Format the track URL
            if artist_name:
                search_query = urllib.parse.quote(f"{track_name} {artist_name}")
            else:
                search_query = urllib.parse.quote(track_name)
            
            url = f"https://open.spotify.com/search/{search_query}"
            webbrowser.open(url)
            
            return f"Opening '{track_name}' on Spotify. Click the play button to start listening!"
        except Exception as e:
            return f"Error opening track: {str(e)}"
    
    def open_artist(self, artist_name: str) -> str:
        """Open an artist page on Spotify"""
        try:
            search_query = urllib.parse.quote(artist_name)
            url = f"https://open.spotify.com/search/{search_query}"
            webbrowser.open(url)
            
            return f"Opening {artist_name}'s page on Spotify. Browse their music and click play to listen!"
        except Exception as e:
            return f"Error opening artist: {str(e)}"
    
    def open_playlist(self, playlist_name: str) -> str:
        """Open a playlist on Spotify"""
        try:
            search_query = urllib.parse.quote(playlist_name)
            url = f"https://open.spotify.com/search/{search_query}"
            webbrowser.open(url)
            
            return f"Opening playlist '{playlist_name}' on Spotify. Click play to start the playlist!"
        except Exception as e:
            return f"Error opening playlist: {str(e)}"
    
    def open_spotify_home(self) -> str:
        """Open Spotify home page"""
        try:
            url = "https://open.spotify.com/"
            webbrowser.open(url)
            
            return "Opening Spotify web player. Browse and play your favorite music!"
        except Exception as e:
            return f"Error opening Spotify: {str(e)}"
    
    def open_spotify_charts(self) -> str:
        """Open Spotify charts"""
        try:
            url = "https://open.spotify.com/charts"
            webbrowser.open(url)
            
            return "Opening Spotify charts. Discover trending music!"
        except Exception as e:
            return f"Error opening charts: {str(e)}"
    
    def open_spotify_new_releases(self) -> str:
        """Open new releases on Spotify"""
        try:
            url = "https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO"
            webbrowser.open(url)
            
            return "Opening new releases on Spotify. Check out the latest music!"
        except Exception as e:
            return f"Error opening new releases: {str(e)}"

# Helper functions
def format_spotify_free_response(response: str) -> str:
    """Format Spotify free response for voice output"""
    return response

def get_spotify_free_help() -> str:
    """Get help for Spotify free features"""
    return """Spotify Free Features:
    - Say "search Spotify for [song/artist]" to search
    - Say "play [song] on Spotify" to open the track
    - Say "open [artist] on Spotify" to browse an artist
    - Say "open Spotify" to go to the home page
    - Say "show me charts on Spotify" for trending music
    - Say "new releases on Spotify" for latest music
    
    Note: You'll need to click play manually in the web player.""" 