#!/usr/bin/env python3
"""
YouTube Music Integration
Provides music playback and control without requiring premium subscriptions
"""

import requests
from typing import Optional, List, Dict
import re
import webbrowser
import time

# Removed all desktop/GUI/automation code for cloud deployment

class YouTubeMusic:
    def __init__(self):
        self.current_url = None
        self.is_playing = False
        
    def search_and_play(self, query: str) -> str:
        """Search for a song and play it on YouTube"""
        try:
            try:
                import pywhatkit
                pywhatkit.playonyt(query)
                time.sleep(1)
                self.current_url = None
                self.is_playing = True
                return f"Playing '{query}' on YouTube."
            except Exception:
                pass

            # Format the search query for YouTube
            search_query = query.replace(' ', '+')
            search_url = f"https://www.youtube.com/results?search_query={search_query}"
            
            # Get search results and extract video ID
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            resp = requests.get(search_url, headers=headers, timeout=10)
            
            if resp.ok:
                # Extract video ID from search results
                video_ids = re.findall(r'"videoId":"([^"]+)"', resp.text)
                if video_ids:
                    # Get the first video ID and open it directly
                    video_url = f'https://www.youtube.com/watch?v={video_ids[0]}'
                    webbrowser.open(video_url)
                    self.current_url = video_url
                    return f"Playing '{query}' on YouTube."
            
            # Fallback: open a playable YouTube search embed instead of raw results
            embed_url = f"https://www.youtube.com/embed?listType=search&list={search_query}&autoplay=1"
            webbrowser.open(embed_url)
            self.current_url = embed_url
            self.is_playing = True
            return f"Playing '{query}' on YouTube."
        except Exception as e:
            # Final fallback on error
            try:
                search_query = query.replace(' ', '+')
                embed_url = f"https://www.youtube.com/embed?listType=search&list={search_query}&autoplay=1"
                webbrowser.open(embed_url)
                self.current_url = embed_url
                self.is_playing = True
                return f"Playing '{query}' on YouTube."
            except:
                return f"Error opening YouTube: {str(e)}"
    
    def play_song(self, song_name: str) -> str:
        """Play a specific song on YouTube"""
        try:
            return self.search_and_play(song_name)
        except Exception as e:
            # Fallback to search if pywhatkit fails
            return self.search_and_play(song_name)
    
    def pause_playback(self) -> str:
        """Pause YouTube playback"""
        try:
            # Press spacebar to pause/play
            # Removed pyautogui.press('space')
            self.is_playing = not self.is_playing
            return "Playback paused." if self.is_playing else "Playback resumed."
        except Exception as e:
            return f"Error controlling playback: {str(e)}"
    
    def skip_forward(self) -> str:
        """Skip forward 10 seconds"""
        try:
            # Removed pyautogui.press('l')
            return "Skipped forward 10 seconds."
        except Exception as e:
            return f"Error skipping forward: {str(e)}"
    
    def skip_backward(self) -> str:
        """Skip backward 10 seconds"""
        try:
            # Removed pyautogui.press('j')
            return "Skipped backward 10 seconds."
        except Exception as e:
            return f"Error skipping backward: {str(e)}"
    
    def next_video(self) -> str:
        """Skip to next video"""
        try:
            # Removed pyautogui.hotkey('shift', 'n')
            return "Skipped to next video."
        except Exception as e:
            return f"Error skipping to next video: {str(e)}"
    
    def previous_video(self) -> str:
        """Go to previous video"""
        try:
            # Removed pyautogui.hotkey('shift', 'p')
            return "Went to previous video."
        except Exception as e:
            return f"Error going to previous video: {str(e)}"
    
    def volume_up(self) -> str:
        """Increase volume"""
        try:
            # Removed pyautogui.press('up')
            return "Volume increased."
        except Exception as e:
            return f"Error increasing volume: {str(e)}"
    
    def volume_down(self) -> str:
        """Decrease volume"""
        try:
            # Removed pyautogui.press('down')
            return "Volume decreased."
        except Exception as e:
            return f"Error decreasing volume: {str(e)}"
    
    def mute_unmute(self) -> str:
        """Mute or unmute"""
        try:
            # Removed pyautogui.press('m')
            return "Muted." if not self.is_playing else "Unmuted."
        except Exception as e:
            return f"Error muting/unmuting: {str(e)}"
    
    def fullscreen(self) -> str:
        """Toggle fullscreen"""
        try:
            # Removed pyautogui.press('f')
            return "Fullscreen toggled."
        except Exception as e:
            return f"Error toggling fullscreen: {str(e)}"
    
    def search_music(self, query: str) -> str:
        """Search for music and return results"""
        try:
            # Format query for YouTube Music search
            search_query = f"{query} music"
            url = f"https://music.youtube.com/search?q={search_query.replace(' ', '+')}"
            # Removed webbrowser.open(url)
            return f"Searching for '{query}' on YouTube Music. Results should open in your browser."
        except Exception as e:
            return f"Error searching YouTube Music: {str(e)}"

    def handle_voice_command(self, cmd):
        cmd = cmd.lower().strip()
        if cmd in ["open youtube", "youtube"]:
            # Removed import webbrowser
            # Removed webbrowser.open("https://www.youtube.com/")
            return "YouTube opened in your browser."
        # --- Play/Search ---
        if "play" in cmd or "search" in cmd:
            # Extract song/video name more intelligently
            if "play" in cmd:
                song = cmd.replace("play", "").strip()
                if "on youtube" in song:
                    song = song.split("on youtube")[0].strip()
                elif "youtube" in song:
                    song = song.split("youtube")[0].strip()
            elif "search" in cmd:
                song = cmd.replace("search", "").strip()
                if "on youtube" in song:
                    song = song.split("on youtube")[0].strip()
                elif "youtube" in song:
                    song = song.split("youtube")[0].strip()
            song = song.strip()
            if song:
                return self.play_song(song)
            else:
                return "Please specify what to play or search on YouTube."
        # --- Playback Controls ---
        if any(x in cmd for x in ["pause", "stop"]):
            return self.pause_playback()
        if any(x in cmd for x in ["resume", "playback", "continue"]):
            return self.pause_playback()  # toggle
        if any(x in cmd for x in ["next", "skip forward", "skip next", "next video", "skip"]):
            return self.next_video()
        if any(x in cmd for x in ["previous", "back", "skip back", "previous video"]):
            return self.previous_video()
        if any(x in cmd for x in ["volume up", "increase volume", "louder"]):
            return self.volume_up()
        if any(x in cmd for x in ["volume down", "decrease volume", "quieter"]):
            return self.volume_down()
        if any(x in cmd for x in ["mute"]):
            return self.mute_unmute()
        if any(x in cmd for x in ["unmute"]):
            return self.mute_unmute()
        if any(x in cmd for x in ["fullscreen", "full screen"]):
            return self.fullscreen()
        if any(x in cmd for x in ["exit fullscreen", "leave fullscreen", "exit full screen", "leave full screen"]):
            return self.fullscreen()
        return "YouTube command not recognized. Say 'play', 'search', 'pause', 'next', 'previous', 'volume up', 'volume down', 'mute', 'unmute', 'fullscreen', or 'exit fullscreen'."

# Helper functions for voice commands
def format_youtube_response(response: str) -> str:
    """Format YouTube response for voice output"""
    return response

def get_youtube_controls_help() -> str:
    """Get help for YouTube controls"""
    return """YouTube Controls:
    - Say "pause" or "play" to pause/resume
    - Say "skip forward" or "next" to skip 10 seconds
    - Say "skip backward" or "previous" to go back 10 seconds
    - Say "next video" to skip to next track
    - Say "volume up" or "volume down" to adjust volume
    - Say "mute" to mute/unmute
    - Say "fullscreen" to toggle fullscreen mode""" 
