import webbrowser
import json
import os
from urllib.parse import urlparse, parse_qs
from spotify_integration import SpotifyIntegration

class SpotifyAuth:
    def __init__(self):
        self.spotify = SpotifyIntegration()
        self.token_file = "spotify_tokens.json"
    
    def authenticate(self) -> bool:
        """Complete Spotify authentication flow"""
        print("🎵 Starting Spotify authentication...")
        
        # Check if we already have valid tokens
        if self.load_tokens():
            if self.spotify.is_authenticated():
                print("✅ Already authenticated with Spotify!")
                return True
        
        # Get authorization URL
        auth_url = self.spotify.get_auth_url()
        print(f"\n🔗 Please visit this URL to authorize Alpha:")
        print(f"{auth_url}")
        print("\nAfter authorization, you'll be redirected to a URL that looks like:")
        print("http://localhost:3000/callback?code=YOUR_AUTH_CODE")
        print("\nCopy the 'code' parameter from that URL and paste it here.")
        
        # Open browser automatically
        try:
            webbrowser.open(auth_url)
            print("🌐 Opening browser automatically...")
        except:
            print("⚠️  Could not open browser automatically. Please copy and paste the URL above.")
        
        # Get auth code from user
        auth_code = input("\n📋 Enter the authorization code: ").strip()
        
        if not auth_code:
            print("❌ No authorization code provided")
            return False
        
        # Exchange code for tokens
        if self.spotify.get_access_token(auth_code):
            # Save tokens
            self.save_tokens()
            print("✅ Spotify authentication successful!")
            return True
        else:
            print("❌ Failed to authenticate with Spotify")
            return False
    
    def save_tokens(self):
        """Save tokens to file"""
        if not self.spotify.access_token:
            return
        
        token_data = {
            'access_token': self.spotify.access_token,
            'refresh_token': self.spotify.refresh_token,
            'expires_at': self.spotify.token_expiry
        }
        
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
            print(f"💾 Tokens saved to {self.token_file}")
        except Exception as e:
            print(f"⚠️  Could not save tokens: {e}")
    
    def load_tokens(self) -> bool:
        """Load tokens from file"""
        if not os.path.exists(self.token_file):
            return False
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            self.spotify.access_token = token_data.get('access_token')
            self.spotify.refresh_token = token_data.get('refresh_token')
            self.spotify.token_expiry = token_data.get('expires_at', 0)
            
            print(f"📂 Tokens loaded from {self.token_file}")
            return True
            
        except Exception as e:
            print(f"⚠️  Could not load tokens: {e}")
            return False
    
    def get_status(self) -> str:
        """Get authentication status"""
        return self.spotify.get_auth_status()

def main():
    """Main function for testing authentication"""
    auth = SpotifyAuth()
    
    print("🎵 Spotify Authentication for Alpha")
    print("=" * 40)
    
    status = auth.get_status()
    print(f"Status: {status}")
    
    if "not configured" in status.lower():
        print("\n❌ Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env file")
        print("Get these from: https://developer.spotify.com/dashboard")
        return
    
    if "not authenticated" in status.lower():
        print("\n🔐 Need to authenticate...")
        if auth.authenticate():
            print("✅ Authentication successful!")
        else:
            print("❌ Authentication failed!")
    else:
        print("✅ Already authenticated!")

if __name__ == "__main__":
    main() 