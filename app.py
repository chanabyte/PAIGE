"""
app.py — GPIO button listener (or CLI integration mode).
Press GPIO button once to START recording, press again to STOP and process.

Modes:
  - Default:        python app.py         → GPIO17 button toggle + background AI processing
  - Interactive:    python app.py --integration  → Manual press-Enter recording (no GPIO)
"""

import signal
import sys
import threading
import time
from gpiozero import Button
import config
import Audio.recorder as recorder
import Gemini.ai as ai


def _send_to_ai(wav_path):
    """Process recording in background thread."""
    ai.process(wav_path)


def on_button_press():
    """Toggle recording on GPIO button press."""
    if recorder.is_recording():
        saved = recorder.stop()
        if saved:
            print(f"\n✓ Recording stopped. Processing with Gemini...")
            threading.Thread(target=_send_to_ai, args=(saved,), daemon=True).start()
    else:
        wav_file = recorder.start()
        print(f"\n[REC] Started recording → {wav_file}")


def integration_mode():
    """Interactive recording mode (for testing without GPIO hardware)."""
    print("\n" + "="*60)
    print("PAIGE — Integration Mode (Interactive)")
    print("="*60)
    
    try:
        while True:
            print("\n[1/3] Recording... Press Enter when done:")
            input()
            
            wav_file = recorder.start()
            print(f"    Recording to: {wav_file}")
            print("    Speak your command now (press Enter to stop):")
            input()
            
            saved = recorder.stop()
            if not saved:
                print("❌ Recording failed!")
                continue
            
            print(f"✓ Saved: {saved}\n")
            
            print("[2/3] Sending to Gemini for transcription & AI processing...")
            try:
                result = ai.process(saved)
                print(f"✓ Processed successfully\n")
            except Exception as e:
                print(f"❌ Gemini processing failed: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            print("[3/3] Results:")
            print("-" * 60)
            print(result)
            print("-" * 60)
            print("✓ Processing complete!\n")
            
            again = input("Record another? (y/n): ").strip().lower()
            if again != "y":
                break
        
        print("\n✓ Done! Goodbye.\n")
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user.")
        if recorder.is_recording():
            recorder.stop()
        sys.exit(0)


def gpio_mode():
    """GPIO button toggle mode - press to start, press to stop."""
    print("\n" + "="*70)
    print("PAIGE — GPIO Mode")
    print("="*70)
    print(f"\n✓ Button on GPIO{config.GPIO_PIN}")
    print("  Press button to START recording")
    print("  Press button again to STOP recording + process with Gemini")
    print("  Press Ctrl+C to exit\n")
    
    button = None
    try:
        button = Button(config.GPIO_PIN, pull_up=True, bounce_time=0.1)
        button.when_pressed = on_button_press
        
        # Keep program running
        signal.pause()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user.")
        if recorder.is_recording():
            recorder.stop()
        if button:
            button.close()
        sys.exit(0)
    except RuntimeError as e:
        if "GPIO" in str(e) or "busy" in str(e).lower():
            print(f"\n❌ GPIO error: {e}")
            print(f"GPIO{config.GPIO_PIN} is busy or unavailable.\n")
            print("Try:")
            print(f"  1. Kill other Python processes: pkill -f 'python.*app.py'")
            print(f"  2. Reset GPIO: gpioset 0 {config.GPIO_PIN}=0")
            print(f"  3. Try again: python app.py\n")
        else:
            print(f"\n❌ Error: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        if button:
            button.close()
        sys.exit(1)


if __name__ == "__main__":
    # Check for integration mode flag
    if "--integration" in sys.argv or "-i" in sys.argv:
        integration_mode()
    else:
        # GPIO button toggle mode
        gpio_mode()
