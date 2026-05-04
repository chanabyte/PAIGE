# PAIGE

Button-controlled voice assistant on Raspberry Pi. Press the button to record, press again to stop — audio is sent to Gemini AI and the response is spoken aloud.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo apt-get install -y espeak-ng mpg123
```

Add your Gemini API key to `.env`:
```
GEMINI_API_KEY=your_key_here
```

## Google Calendar (Headless Sign-In)

PAIGE supports a single active Google user via an OAuth **limited-input device flow**.
This works without a monitor: PAIGE will give you a URL + code to enter on your phone.

1) Create an OAuth client ID in Google Cloud Console that supports limited-input devices.

2) Add to `.env`:
```
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...  # optional
```

3) Ask PAIGE to connect:
- Say something like: "connect my calendar"
- Follow the URL + code on your phone
- Then ask again (or ask for events): "what's on my calendar?"

To sign out: "disconnect my calendar"

## Run

```bash
python app.py
```

## Wiring

Button connected to **GPIO17 (BCM)** → GND (internal pull-up enabled).

---

## Voice Options

Change `_VOICE` in `ai.py` to swap the text-to-speech voice.

Personal favourite was **Sonia**, but choose any below:

```python
# United States
_VOICE = "en-US-GuyNeural"
_VOICE = "en-US-JennyNeural"
_VOICE = "en-US-AriaNeural"
_VOICE = "en-US-AvaNeural"
_VOICE = "en-US-AndrewNeural"
_VOICE = "en-US-EmmaNeural"
_VOICE = "en-US-BrianNeural"
_VOICE = "en-US-ChristopherNeural"
_VOICE = "en-US-EricNeural"
_VOICE = "en-US-MichelleNeural"
_VOICE = "en-US-RogerNeural"
_VOICE = "en-US-SteffanNeural"
_VOICE = "en-US-AnaNeural"
_VOICE = "en-US-EmmaMultilingualNeural"
_VOICE = "en-US-AndrewMultilingualNeural"
_VOICE = "en-US-AvaMultilingualNeural"
_VOICE = "en-US-BrianMultilingualNeural"

# United Kingdom
_VOICE = "en-GB-SoniaNeural"           # ⭐ personal favourite
_VOICE = "en-GB-RyanNeural"
_VOICE = "en-GB-LibbyNeural"
_VOICE = "en-GB-MaisieNeural"
_VOICE = "en-GB-ThomasNeural"

# Australia
_VOICE = "en-AU-WilliamMultilingualNeural"
_VOICE = "en-AU-NatashaNeural"

# Canada
_VOICE = "en-CA-ClaraNeural"
_VOICE = "en-CA-LiamNeural"

# India
_VOICE = "en-IN-NeerjaExpressiveNeural"
_VOICE = "en-IN-NeerjaNeural"
_VOICE = "en-IN-PrabhatNeural"

# Ireland
_VOICE = "en-IE-ConnorNeural"
_VOICE = "en-IE-EmilyNeural"

# Singapore
_VOICE = "en-SG-LunaNeural"
_VOICE = "en-SG-WayneNeural"

# South Africa
_VOICE = "en-ZA-LeahNeural"
_VOICE = "en-ZA-LukeNeural"

# Hong Kong
_VOICE = "en-HK-YanNeural"
_VOICE = "en-HK-SamNeural"

# New Zealand
_VOICE = "en-NZ-MitchellNeural"
_VOICE = "en-NZ-MollyNeural"

# Nigeria
_VOICE = "en-NG-AbeoNeural"
_VOICE = "en-NG-EzinneNeural"

# Philippines
_VOICE = "en-PH-JamesNeural"
_VOICE = "en-PH-RosaNeural"

# Kenya
_VOICE = "en-KE-AsiliaNeural"
_VOICE = "en-KE-ChilembaNeural"

# Tanzania
_VOICE = "en-TZ-ElimuNeural"
_VOICE = "en-TZ-ImaniNeural"
```
