#!/usr/bin/env python3

import asyncio
import socketio

async def test_basic_connection():
    """Test basic Socket.IO connection"""
    print("🧪 Testing basic Socket.IO connection...")
    
    sio = socketio.AsyncClient()
    
    @sio.event
    async def connect():
        print("✅ Connected to server")
        
    @sio.event
    async def connected(data):
        print(f"✅ Received connected event: {data}")
        
    @sio.event
    async def disconnect():
        print("❌ Disconnected from server")
    
    try:
        # Connect to the server
        await sio.connect('http://localhost:8000')
        print("✅ Connection established")
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Disconnect
        await sio.disconnect()
        print("✅ Disconnected cleanly")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_basic_connection())
    if result:
        print("🎉 Basic Socket.IO test PASSED")
    else:
        print("💥 Basic Socket.IO test FAILED") 