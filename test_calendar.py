#!/usr/bin/env python3
"""
Test script for Google Calendar API integration.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Google import calendar_api

print("=== PAIGE Calendar API Test ===\n")

# Step 1: Connect
print("1. Connecting to Google Calendar...")
result = calendar_api.connect_calendar()
print(f"   Result: {result}\n")

if result.get("status") == "pending":
    print(f"   📱 Go to: {result['verification_url']}")
    print(f"   📝 Enter code: {result['user_code']}\n")
    input("   Press Enter after authorizing in your browser...")
    result = calendar_api.connect_calendar()
    print(f"   Result: {result}\n")

# Step 2: List events
print("2. Listing upcoming events...")
events = calendar_api.list_upcoming_events(max_results=3)
if "error" in events:
    print(f"   ❌ Error: {events['error']}")
else:
    print(f"   ✓ Found {len(events.get('events', []))} events:")
    for ev in events.get("events", []):
        print(f"     - {ev['summary']} ({ev['start']})")
print()

# Step 3: Create an event
print("3. Creating a test event...")
create_result = calendar_api.create_event(
    title="PAIGE Test Event",
    description="Created by the test script",
    hours_from_now=0.5
)
if "error" in create_result:
    print(f"   ❌ Error: {create_result['error']}")
else:
    print(f"   ✓ Event created!")
    print(f"     Title: {create_result['title']}")
    print(f"     Start: {create_result['start']}")
print()

# Step 4: List again to verify
print("4. Listing events again to verify creation...")
events = calendar_api.list_upcoming_events(max_results=3)
if "error" in events:
    print(f"   ❌ Error: {events['error']}")
else:
    print(f"   ✓ Found {len(events.get('events', []))} events:")
    for ev in events.get("events", []):
        print(f"     - {ev['summary']} ({ev['start']})")

print("\n✅ Calendar API test complete!")
