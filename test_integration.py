"""
test_integration.py — Automated full flow: record → Gemini → function call → calendar.

Run this for quick end-to-end testing without manual input.
Records for ~5 seconds, then processes through Gemini AI with function calling.
"""

import sys
import time
from pathlib import Path

import Audio.recorder as recorder
import Gemini.ai as ai


def auto_record_and_process(duration_seconds=5):
    """Record audio for a fixed duration, then process through full pipeline."""
    print("\n" + "="*70)
    print(" AUTOMATED INTEGRATION TEST: Record → Gemini AI → Function Calling")
    print("="*70)
    
    # STEP 1: Record for fixed duration
    print(f"\n[1/3] Recording for {duration_seconds} seconds...")
    wav_file = recorder.start()
    print(f"      → {wav_file}")
    
    try:
        time.sleep(duration_seconds)
    except KeyboardInterrupt:
        print("\n⚠ Interrupted!")
        recorder.stop()
        return False
    
    saved = recorder.stop()
    if not saved:
        print("❌ Recording failed!")
        return False
    
    file_size = saved.stat().st_size if saved.exists() else 0
    print(f"      ✓ Saved {file_size} bytes\n")
    
    # STEP 2: Send to Gemini for transcription + function calling + calendar processing
    print("[2/3] Processing with Gemini AI...")
    print("      • Uploading audio file")
    print("      • Transcribing (speech-to-text)")
    print("      • Analyzing with AI")
    print("      • Checking for function calls (calendar, weather, etc.)")
    
    try:
        result = ai.process(saved)
        print(f"      ✓ AI processing complete\n")
    except Exception as e:
        print(f"❌ Gemini processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # STEP 3: Display results
    print("[3/3] Full Results:")
    print("-" * 70)
    print(result)
    print("-" * 70)
    print("✓ Complete! \n")
    
    return True


def main():
    """Main entry point."""
    print("\nUsage: python test_integration.py [duration_seconds]")
    print("  Duration defaults to 5 seconds if not specified.\n")
    
    # Get duration from command line if provided
    duration = 5
    if len(sys.argv) > 1:
        try:
            duration = float(sys.argv[1])
            print(f"Recording duration set to {duration} seconds.\n")
        except ValueError:
            print(f"Invalid duration '{sys.argv[1]}', using default 5 seconds.\n")
    
    try:
        success = auto_record_and_process(duration_seconds=duration)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user.")
        if recorder.is_recording():
            recorder.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
