"""Shared command queue between Gemini tools and the UI."""
import queue

CMD: queue.Queue = queue.Queue()
