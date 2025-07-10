import os
import sys
import json
import time
import webbrowser
from pathlib import Path
import logging

# Import Spotify-related modules
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False
    logging.warning("Spotipy not installed. Spotify functionality will be limited.")

# Import QT components for dialog
try:
    from PyQt6.QtWidgets import QInputDialog, QMessageBox
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    logging.warning("PyQt6 not available. Will use console for authentication.")


class SpotifyAuthManager:
    """
    A class to handle Spotify authentication across different modules.
    Manages token acquisition, refreshing, and provides a configured Spotify client.
    """
    
    # Define all possible scopes for maximum flexibility
    ALL_SCOPES = [
        # Listening History
        'user-read-recently-played',
        'user-top-read',
        'user-read-playback-position',
        
        # Spotify Connect
        'user-read-playback-state',
        'user-modify-playback-state',
        'user-read-currently-playing',
        
        # Playback
        # 'streaming',
        # 'app-remote-control',
        
        # Playlists
        'playlist-read-private',
        'playlist-read-collaborative',
        'playlist-modify-private',
        'playlist-modify-public',
        
        # Library
        'user-library-modify',
        'user-library-read',
        
        # Users
        'user-read-email',
        'user-read-private',
        
        # Follow
        'user-follow-read',
        'user-follow-modify'
    ]
    
# In the SpotifyAuthManager class:

    def __init__(self, client_id=None, client_secret=None, redirect_uri=None, 
                cache_path=None, project_root=None, parent_widget=None, selected_scopes=None):
        """
        Initialize the Spotify Authentication Manager.
        
        Args:
            client_id (str): Spotify API client ID
            client_secret (str): Spotify API client secret
            redirect_uri (str, optional): Redirect URI for OAuth flow.
            cache_path (str, optional): Path to store the authentication token.
            project_root (str, optional): Root path of the application.
            parent_widget (QWidget, optional): Parent widget for dialogs.
            selected_scopes (list, optional): List of specific scopes to request. If None, uses all.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        
        # If redirect_uri is None, check for one in config or use default
        if redirect_uri is None:
            # Try to get redirect URI from config if possible
            try:
                sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                from base_module import PROJECT_ROOT
                import yaml
                config_path = PROJECT_ROOT / "config" / "config.yml"
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    spotify_config = config.get('global_theme_config', {})
                    redirect_uri = spotify_config.get('spotify_redirect_uri', "http://localhost:8998")
                else:
                    redirect_uri = "http://localhost:8998"
            except Exception:
                # Default fallback
                redirect_uri = "http://localhost:8998"
        
        self.redirect_uri = redirect_uri

        self.parent_widget = parent_widget
        self.logger = logging.getLogger("SpotifyAuthManager")
        
        # Try to determine PROJECT_ROOT if not provided
        if project_root:
            self.PROJECT_ROOT = Path(project_root)
        else:
            # Try to get it from the global variable if available
            try:
                sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                from base_module import PROJECT_ROOT
                self.PROJECT_ROOT = PROJECT_ROOT
            except ImportError:
                # Fallback to current directory
                self.PROJECT_ROOT = Path.cwd()
        
        # Set up cache path
        if cache_path:
            self.cache_path = cache_path
        else:
            cache_dir = self.PROJECT_ROOT / ".content" / "cache"
            os.makedirs(cache_dir, exist_ok=True)
            self.cache_path = str(cache_dir / "spotify_token.txt")
        
        # Set up scopes
        self.scopes = selected_scopes if selected_scopes else self.ALL_SCOPES
        
        # Initialize variables
        self.sp_oauth = None
        self.token_info = None
        self.spotify_client = None
        self.user_info = None
        
        # Check if spotipy is available
        if not SPOTIPY_AVAILABLE:
            self.logger.error("Spotipy library not available. Please install with 'pip install spotipy'")
            return
            
        # Setup OAuth handler
        self._setup_oauth()
        
        # Try to load existing token
        self._load_token()
    
    def _setup_oauth(self):
        """Set up the SpotifyOAuth object with appropriate configurations."""
        if not SPOTIPY_AVAILABLE:
            return
            
        if not self.client_id or not self.client_secret:
            self.logger.warning("Spotify client_id or client_secret not provided")
            return
            
        try:
            self.sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=' '.join(self.scopes),
                cache_path=self.cache_path,
                open_browser=False
            )
            self.logger.info("SpotifyOAuth object initialized successfully")
        except Exception as e:
            self.logger.error(f"Error setting up SpotifyOAuth: {e}")
            self.sp_oauth = None
    
    def _load_token(self):
        """Load the cached token if available."""
        if not self.sp_oauth:
            return False
            
        try:
            self.token_info = self.sp_oauth.get_cached_token()
            if self.token_info and 'access_token' in self.token_info:
                self.logger.info("Loaded cached Spotify token")
                # Create a Spotify client with the token
                self._create_spotify_client()
                return True
            else:
                self.logger.info("No valid cached token found")
                return False
        except Exception as e:
            self.logger.error(f"Error loading cached token: {e}")
            return False
    
    def _create_spotify_client(self):
        """Create a Spotify client using the current token."""
        if not SPOTIPY_AVAILABLE or not self.token_info:
            return False
            
        try:
            self.spotify_client = spotipy.Spotify(auth=self.token_info['access_token'])
            
            # Try to get user info to validate the token
            self.user_info = self.spotify_client.current_user()
            if self.user_info and 'id' in self.user_info:
                self.logger.info(f"Spotify client created for user: {self.user_info.get('display_name')}")
                return True
            else:
                self.logger.warning("Could not retrieve user info with the token")
                self.spotify_client = None
                return False
        except Exception as e:
            self.logger.error(f"Error creating Spotify client: {e}")
            self.spotify_client = None
            return False
    
    def _refresh_token_if_needed(self):
        """Check if the token needs refreshing and refresh if necessary."""
        if not self.sp_oauth or not self.token_info:
            return False
            
        try:
            if self.sp_oauth.is_token_expired(self.token_info):
                self.logger.info("Token expired, refreshing...")
                self.token_info = self.sp_oauth.refresh_access_token(self.token_info['refresh_token'])
                # Update the client with the new token
                return self._create_spotify_client()
            return True
        except Exception as e:
            self.logger.error(f"Error refreshing token: {e}")
            return False
    
    def authenticate(self, force_new_auth=False):
        """
        Show a dialog where the user can authenticate with Spotify.
        
        Args:
            force_new_auth (bool): Force a new authentication flow even if a token exists.
                
        Returns:
            bool: True if authentication was successful, False otherwise.
        """
        if not SPOTIPY_AVAILABLE or not self.sp_oauth:
            return False
                
        # If we already have a valid token and are not forcing new auth, just refresh if needed
        if self.token_info and not force_new_auth:
            if self._refresh_token_if_needed():
                return True
            
        # Start the OAuth flow
        try:
            # Get the authorization URL
            auth_url = self.sp_oauth.get_authorize_url()
            self.logger.info(f"Opening browser for Spotify authentication: {auth_url}")
                
            # Create a clickable message box with the URL
            if QT_AVAILABLE and self.parent_widget:
                from PyQt6.QtWidgets import QMessageBox
                from PyQt6.QtCore import Qt
                
                msg = QMessageBox(self.parent_widget)
                msg.setWindowTitle("Spotify Authentication")
                msg.setText(f"Please click the button below to open Spotify login in your browser:")
                msg.setInformativeText(f"After logging in, you will be redirected to a URL. Copy that URL and paste it in the next dialog.")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                msg.setDefaultButton(QMessageBox.StandardButton.Ok)
                
                # Custom button text
                open_button = msg.button(QMessageBox.StandardButton.Ok)
                open_button.setText("Open Spotify Login")
                
                # Show the message box
                result = msg.exec()
                
                if result == QMessageBox.StandardButton.Cancel:
                    self.logger.info("Authentication canceled by user")
                    return False
                    
                # Open browser
                import webbrowser
                webbrowser.open(auth_url)
                
                # Get the redirect URL from the user with a dialog
                from PyQt6.QtWidgets import QInputDialog
                redirect_url, ok = QInputDialog.getText(
                    self.parent_widget,
                    "Spotify Authentication",
                    "Please paste the entire URL you were redirected to:"
                )
                
                if not ok or not redirect_url:
                    self.logger.info("URL input canceled by user")
                    return False
            else:
                # Use console input
                print("\nPlease log in to Spotify in your browser.")
                print("After logging in, you will be redirected to a URL starting with your redirect URI.")
                print("Please copy the entire URL and paste it here:")
                redirect_url = input("Enter the URL you were redirected to: ")
                
            # Process the response
            if redirect_url:
                # Get the code from the URL
                code = self.sp_oauth.parse_response_code(redirect_url)
                
                # Exchange the code for a token
                self.token_info = self.sp_oauth.get_access_token(code)
                
                # Create the Spotify client
                if self._create_spotify_client():
                    self.logger.info("Authentication successful")
                    return True
                    
            self.logger.error("Authentication failed - no valid URL provided")
            return False
                    
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False
    
    def get_client(self):
        """
        Get an authenticated Spotify client.
        
        Returns:
            spotipy.Spotify or None: The authenticated Spotify client or None if authentication fails.
        """
        if not SPOTIPY_AVAILABLE:
            return None
            
        # If we already have a client, refresh the token if needed and return it
        if self.spotify_client:
            if self._refresh_token_if_needed():
                return self.spotify_client
        
        # Otherwise, try to authenticate
        if self.authenticate():
            return self.spotify_client
        
        return None
    
    def clear_token(self):
        """Clear the cached token to force a new authentication."""
        if os.path.exists(self.cache_path):
            try:
                os.remove(self.cache_path)
                self.logger.info(f"Removed cached token at {self.cache_path}")
            except Exception as e:
                self.logger.error(f"Error removing cached token: {e}")
        
        # Reset instance variables
        self.token_info = None
        self.spotify_client = None
        self.user_info = None
        
        # Reinitialize OAuth handler
        self._setup_oauth()
        
        return True
    
    def is_authenticated(self):
        """Check if we have a valid authentication token."""
        if not self.token_info:
            return False
            
        return self._refresh_token_if_needed()
    
    def get_user_info(self):
        """
        Get information about the authenticated user.
        
        Returns:
            dict or None: User information or None if not authenticated.
        """
        if not self.is_authenticated():
            return None
            
        try:
            self.user_info = self.spotify_client.current_user()
            return self.user_info
        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return None