# CEASER Desktop Production Setup

## Pre-Installation Configuration

Before installing CEASER on a new machine, you must set up your API keys.

### Step 1: Create .env File

Copy the `.env.example` file to `.env` in one of these locations (in order of priority):

1. **AppData (Recommended for installed app)**:
   ```
   %APPDATA%/CEASER/.env
   ```
   Example path: `C:\Users\YourUsername\AppData\Roaming\CEASER\.env`

2. **Desktop folder**:
   ```
   C:\Users\YourUsername\Desktop\ceaser\.env
   ```

3. **Installer directory**:
   ```
   C:\Program Files\CEASER\.env
   ```

### Step 2: Add Required API Keys

Edit your `.env` file and add:

```
# Deepgram for voice transcription (REQUIRED for voice commands)
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# ElevenLabs for voice output (optional)
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# Backend API
CEASER_API_URL=https://ceaser-backend-production-ur04.onrender.com

# Frontend App URL
CEASER_APP_URL=https://app.ceaser.ai
```

### Step 3: Get Your API Keys

**Deepgram** (required for voice):
1. Go to https://console.deepgram.com
2. Create a free account
3. Get your API key from the settings
4. Add it to `.env`

**ElevenLabs** (optional for better voice):
1. Go to https://elevenlabs.io
2. Create a free account
3. Get your API key
4. Add it to `.env`

## Installation

1. Download `CEASER Setup 0.1.0.exe` from the release folder
2. Run the installer and choose your installation directory
3. Complete the installation
4. Create the `.env` file as described above
5. Restart CEASER

## First Launch

When you first launch CEASER:

1. The main window will open with the full application
2. You can use text commands immediately
3. For voice commands, you'll need the DEEPGRAM_API_KEY configured
4. Press `Ctrl+Shift+Space` to show the voice overlay
5. Say "Hey CEASER" followed by your command

## Troubleshooting

### Voice Assistant Not Working

**Error**: "Microphone unavailable"
- Check Windows Sound settings: Settings → Privacy & Security → Microphone
- Make sure CEASER has microphone permission
- Restart CEASER after granting permission

**Error**: "Deepgram key is not configured"
- Add `DEEPGRAM_API_KEY` to your `.env` file
- Place `.env` in `%APPDATA%/CEASER/` directory
- Restart CEASER

**Error**: "Voice transcription failed"
- Verify your Deepgram API key is correct
- Check internet connection
- Try re-recording with clearer audio

### App Not Starting

- Check that the `.env` file exists and is valid
- Delete `.env` and let CEASER create a default one
- Reinstall the application

### Hotkey Not Working (Ctrl+Shift+Space)

- Check if another app is using this hotkey
- Try a different hotkey combination (may need code update)
- Restart CEASER

## Production Deployment Checklist

- [ ] `.env` file configured with all API keys
- [ ] DEEPGRAM_API_KEY added (for voice)
- [ ] Test voice command: "Hey CEASER, what time is it?"
- [ ] Test text command: type a command in the input
- [ ] Verify window controls (minimize, maximize, close)
- [ ] Test overlay hotkey: Ctrl+Shift+Space
- [ ] Verify data is not stored locally (all data goes to backend)
- [ ] Check logs in browser console (F12) for errors

## Security Notes

- `.env` files contain sensitive API keys - keep them private
- Never commit `.env` files to version control
- Store `.env` in user's AppData folder (`%APPDATA%/CEASER/.env`)
- API keys are only used locally to communicate with cloud services
- No data is stored on the local machine
