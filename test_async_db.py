"""
Quick async database functionality test
"""

import asyncio
from database_async import (
    get_async_session,
    fetch_enabled_bots_async,
    fetch_enabled_chats_async,
    fetch_all_settings_async,
)


async def test_async_queries():
    """Test async query functions"""
    print("=== Async Database Functionality Test ===\n")

    async with get_async_session() as session:
        # Test 1: Fetch enabled bots
        print("Test 1: Fetching enabled bots...")
        bots = await fetch_enabled_bots_async(session)
        print(f"  Result: Found {len(bots)} enabled bots")
        for bot in bots[:3]:  # Show first 3
            print(f"    - {bot.name} (ID: {bot.id})")

        # Test 2: Fetch enabled chats
        print("\nTest 2: Fetching enabled chats...")
        chats = await fetch_enabled_chats_async(session)
        print(f"  Result: Found {len(chats)} enabled chats")
        for chat in chats[:3]:
            print(f"    - {chat.title or 'Untitled'} (chat_id: {chat.chat_id})")

        # Test 3: Fetch settings
        print("\nTest 3: Fetching settings...")
        settings = await fetch_all_settings_async(session)
        print(f"  Result: Found {len(settings)} settings")
        # Show a few important ones
        for key in ["simulation_active", "scale_factor", "max_msgs_per_min"]:
            value = settings.get(key, "NOT_FOUND")
            print(f"    - {key}: {value}")

    print("\n=== All Tests Passed ===")


if __name__ == "__main__":
    asyncio.run(test_async_queries())
