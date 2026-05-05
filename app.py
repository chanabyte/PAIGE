"""PAIGE — main entry point."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Display.paige_ui import run

if __name__ == "__main__":
    run()
