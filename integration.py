"""
integration.py — Full recording → Gemini AI → Function Calling → Calendar flow.

Run this to:
1. Record audio from microphone
2. Transcribe + get Gemini AI response with function calling
3. Execute any calendar operations automatically
4. Display results
"""

import sys
from pathlib import Path

import Audio.recorder as recorder
import Gemini.ai as ai


def record_and_process():
    """Record audio, transcribe, call functions, return to calendar."""
    print("\n" + "="*60)
    print("PAIGE — Audio Recording & Gemini Processing")
    print("="*60)
    
    # STEP 1: Record audio
    print("\n[1/3] Recording... Press Enter when done:")
    input()
    
    wav_file = recorder.start()
    print(f"    Recording to: {wav_file}")
    print("    Speak your command now (press Enter to stop):")
    input()
    
    saved = recorder.stop()
    if not saved:
        print("❌ Recording failed!")
        return False
    
    print(f"✓ Saved: {saved}\n")
    
    # STEP 2: Send to Gemini for transcription + function calling
    print("[2/3] Sending to Gemini for transcription & AI processing...")
    try:
        result = ai.process(saved)
        print(f"✓ Processed successfully\n")
    except Exception as e:
        print(f"❌ Gemini processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # STEP 3: Display results
    print("[3/3] Results:")
    print("-" * 60)
    print(result)
    print("-" * 60)
    print("✓ Processing complete!\n")
    
    return True


def main():
    try:
        while True:
            success = record_and_process()
            if not success:
                break
            
            again = input("\nRecord another? (y/n): ").strip().lower()
            if again != "y":
                break
        
        print("\n✓ Done! Goodbye.\n")
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user.")
        if recorder.is_recording():
            recorder.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
