# Spotify Lyrics Overlay

This application displays synchronized lyrics for the currently playing song on Spotify in a modern, customizable overlay window.

## Features

*   Displays current and upcoming lyric lines.
*   Fetches lyrics from LRCLIB and Megalobiz.
*   Customizable background color based on album art.
*   Modern UI using PySide6.
*   System tray icon for easy access (Show/Hide, Exit).
*   Authentication handled via Spotify API (OAuth 2.0).

## Prerequisites

*   Python 3.7+
*   A Spotify Premium account (required by the Spotify API for playback control and information).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    The application uses several Python libraries. You'll need to install them.
    A `requirements.txt` file would typically be used here. For now, you'll need to install them manually:
    ```bash
    pip install requests pyside6 pystray beautifulsoup4 Pillow
    ```
    *(Developer Note: Consider adding a `requirements.txt` file for easier dependency management.)*

4.  **Set up Spotify API Credentials:**
    This application requires you to set up your own Spotify API credentials.
    *   Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) and log in or create an account.
    *   Create a new App. You can name it whatever you like (e.g., "Lyrics Overlay").
    *   Once the app is created, you will see your **Client ID**.
    *   Click on "Show client secret" to see your **Client Secret**.
    *   You now need to set these as environment variables:
        *   `SPOTIPY_CLIENT_ID`: Your Spotify application's Client ID.
        *   `SPOTIPY_CLIENT_SECRET`: Your Spotify application's Client Secret.

    **How to set environment variables:**

    *   **Linux/macOS (temporary, for the current session):**
        ```bash
        export SPOTIPY_CLIENT_ID="YOUR_CLIENT_ID"
        export SPOTIPY_CLIENT_SECRET="YOUR_CLIENT_SECRET"
        ```
        For permanent setting, add these lines to your shell's configuration file (e.g., `.bashrc`, `.zshrc`).

    *   **Windows (temporary, for the current session in Command Prompt):**
        ```cmd
        set SPOTIPY_CLIENT_ID="YOUR_CLIENT_ID"
        set SPOTIPY_CLIENT_SECRET="YOUR_CLIENT_SECRET"
        ```
    *   **Windows (temporary, for the current session in PowerShell):**
        ```powershell
        $env:SPOTIPY_CLIENT_ID="YOUR_CLIENT_ID"
        $env:SPOTIPY_CLIENT_SECRET="YOUR_CLIENT_SECRET"
        ```
        For permanent setting, search for "environment variables" in the Windows search bar and add them through the System Properties dialog.

    *   **Using a `.env` file (recommended for local development):**
        Create a file named `.env` in the root directory of the project (alongside `spotify_lyrics_overlay.py`). Add your credentials to this file:
        ```
        SPOTIPY_CLIENT_ID="YOUR_CLIENT_ID"
        SPOTIPY_CLIENT_SECRET="YOUR_CLIENT_SECRET"
        ```
        The `.gitignore` file is already configured to ignore `.env` files, so your secrets won't be committed. You would need to modify the Python script to load these variables from the `.env` file, for example, using the `python-dotenv` library (`pip install python-dotenv`).
        *(Developer Note: The current script version reads directly from environment variables, not a .env file. This is an alternative setup method for users.)*


5.  **Set Redirect URI in Spotify Dashboard:**
    *   In your Spotify App settings on the Developer Dashboard, click "Edit Settings".
    *   Add `https://example.com/callback` to the "Redirect URIs" field.
    *   Click "Save". This URI must match the `redirect_uri` variable in the script.

## Running the Application

Once the setup is complete, run the script:

```bash
python spotify_lyrics_overlay.py
```

*   On the first run (or if `spotify_token.json` is missing/invalid), the script will print an authentication URL in the console.
*   Copy this URL and paste it into your web browser.
*   Log in to Spotify and authorize the application.
*   You will be redirected to a URL like `https://example.com/callback?code=...`.
*   Copy this entire redirect URL and paste it back into the console when prompted.
*   If authentication is successful, a `spotify_token.json` file will be created, and the lyrics overlay should appear.

The overlay window can be dragged around the screen. A tray icon will also appear, allowing you to show/hide the window or exit the application.

## Troubleshooting

*   **"ERRO: As variáveis de ambiente SPOTIPY_CLIENT_ID e SPOTIPY_CLIENT_SECRET não foram definidas."**: Ensure you have correctly set the environment variables as described in step 4 of the Setup section.
*   **Authentication Errors**: Double-check your Client ID, Client Secret, and Redirect URI in the Spotify Developer Dashboard. Ensure the Redirect URI in your dashboard exactly matches `https://example.com/callback`.
*   **No Lyrics Found**: Lyrics availability depends on the sources (LRCLIB, Megalobiz). Not all songs may have synchronized lyrics.
*   **Window not appearing on top**: This can sometimes be an issue with specific desktop environments or other applications.

## Contributing

Feel free to fork the repository, make improvements, and submit pull requests.

## License

This project is open source. Please check for a `LICENSE` file for more details (currently not provided).
*(Developer Note: Consider adding a `LICENSE` file, e.g., MIT License.)*
