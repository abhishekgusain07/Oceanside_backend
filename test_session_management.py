#!/usr/bin/env python3
"""
Test script for robust session management
Tests heartbeat mechanism, graceful shutdowns, and network interruption handling
"""

import asyncio
import aiohttp
import socketio
import time
import json
from datetime import datetime
from typing import Dict, List

class SessionTestClient:
    def __init__(self, server_url: str, user_id: str, user_type: str = 'host'):
        self.server_url = server_url
        self.user_id = user_id
        self.user_type = user_type
        self.room_id = f"test-room-{int(time.time())}"
        self.sio = socketio.AsyncClient()
        self.connected = False
        self.events_received: List[Dict] = []
        
    async def connect(self):
        """Connect to the Socket.IO server"""
        try:
            # Set up event handlers
            self.sio.on('connect', self.on_connect)
            self.sio.on('disconnect', self.on_disconnect)
            self.sio.on('heartbeat_response', self.on_heartbeat_response)
            self.sio.on('host_disconnected', self.on_host_disconnected)
            self.sio.on('guest_left', self.on_guest_left)
            self.sio.on('guest_joined', self.on_guest_joined)
            
            await self.sio.connect(self.server_url)
            await asyncio.sleep(1)  # Wait for connection to stabilize
            
        except Exception as e:
            print(f"❌ Failed to connect {self.user_type} {self.user_id}: {e}")
            return False
        
        return True
    
    async def join_room(self):
        """Join a room"""
        if not self.connected:
            return False
        
        try:
            await self.sio.emit('join_room', self.room_id)
            await asyncio.sleep(0.5)  # Wait for room join
            print(f"✅ {self.user_type} {self.user_id} joined room {self.room_id}")
            return True
        except Exception as e:
            print(f"❌ Failed to join room: {e}")
            return False
    
    async def start_heartbeat(self):
        """Start sending heartbeats"""
        while self.connected:
            try:
                await self.sio.emit('heartbeat', {
                    'roomId': self.room_id,
                    'userId': self.user_id,
                    'userType': self.user_type,
                    'isRecording': False,
                    'timestamp': datetime.now().timestamp() * 1000
                })
                await asyncio.sleep(10)  # Send heartbeat every 10 seconds
            except Exception as e:
                print(f"❌ Heartbeat failed for {self.user_id}: {e}")
                break
    
    async def simulate_recording(self, duration: int = 30):
        """Simulate recording session"""
        if not self.connected or self.user_type != 'host':
            return
        
        print(f"🎬 Starting recording simulation for {duration} seconds...")
        
        # Start recording
        await self.sio.emit('start_recording', {'room_id': self.room_id})
        
        # Simulate recording for specified duration
        for i in range(duration):
            if not self.connected:
                break
            
            # Send heartbeat with recording=True
            await self.sio.emit('heartbeat', {
                'roomId': self.room_id,
                'userId': self.user_id,
                'userType': self.user_type,
                'isRecording': True,
                'timestamp': datetime.now().timestamp() * 1000
            })
            
            await asyncio.sleep(1)
        
        # Stop recording
        if self.connected:
            await self.sio.emit('stop_recording', {'room_id': self.room_id})
            print("🛑 Recording simulation stopped")
    
    async def graceful_leave(self):
        """Leave room gracefully"""
        if not self.connected:
            return
        
        try:
            if self.user_type == 'host':
                await self.sio.emit('host_leaving_room', {
                    'roomId': self.room_id,
                    'userId': self.user_id,
                    'reason': 'user_exit'
                })
            else:
                await self.sio.emit('guest_leaving_room', {
                    'roomId': self.room_id,
                    'userId': self.user_id,
                    'reason': 'user_exit'
                })
            
            await asyncio.sleep(1)  # Wait for cleanup
            print(f"✅ {self.user_type} {self.user_id} left room gracefully")
            
        except Exception as e:
            print(f"❌ Error during graceful leave: {e}")
    
    async def disconnect(self):
        """Disconnect from server"""
        if self.connected:
            await self.sio.disconnect()
    
    # Event handlers
    async def on_connect(self):
        self.connected = True
        print(f"🔗 {self.user_type} {self.user_id} connected")
    
    async def on_disconnect(self):
        self.connected = False
        print(f"💔 {self.user_type} {self.user_id} disconnected")
    
    async def on_heartbeat_response(self, data):
        self.events_received.append({
            'event': 'heartbeat_response',
            'timestamp': datetime.now().isoformat(),
            'data': data
        })
        print(f"💓 Heartbeat response for {self.user_id}: {data.get('status')}")
    
    async def on_host_disconnected(self, data):
        self.events_received.append({
            'event': 'host_disconnected', 
            'timestamp': datetime.now().isoformat(),
            'data': data
        })
        print(f"🚨 Host disconnected: {data}")
    
    async def on_guest_left(self, data):
        self.events_received.append({
            'event': 'guest_left',
            'timestamp': datetime.now().isoformat(), 
            'data': data
        })
        print(f"👋 Guest left: {data}")
    
    async def on_guest_joined(self, data):
        self.events_received.append({
            'event': 'guest_joined',
            'timestamp': datetime.now().isoformat(),
            'data': data
        })
        print(f"👥 Guest joined: {data}")

async def test_basic_heartbeat():
    """Test basic heartbeat functionality"""
    print("\n🧪 Testing basic heartbeat functionality...")
    
    host = SessionTestClient('http://localhost:8000', 'test-host-1', 'host')
    
    heartbeat_task = None
    try:
        # Connect and join room
        if not await host.connect():
            return False
        
        if not await host.join_room():
            return False
        
        # Start heartbeat and run for 30 seconds
        heartbeat_task = asyncio.create_task(host.start_heartbeat())
        await asyncio.sleep(30)
        
        # Check if we received heartbeat responses
        heartbeat_responses = [e for e in host.events_received if e['event'] == 'heartbeat_response']
        
        if len(heartbeat_responses) >= 2:
            print("✅ Basic heartbeat test passed")
            return True
        else:
            print(f"❌ Basic heartbeat test failed - only {len(heartbeat_responses)} responses")
            return False
    
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        await host.graceful_leave()
        await host.disconnect()

async def test_network_interruption():
    """Test network interruption handling"""
    print("\n🧪 Testing network interruption handling...")
    
    host = SessionTestClient('http://localhost:8000', 'test-host-2', 'host')
    guest = SessionTestClient('http://localhost:8000', 'test-guest-1', 'guest')
    guest.room_id = host.room_id  # Same room
    
    try:
        # Connect both clients
        if not await host.connect() or not await host.join_room():
            return False
        
        if not await guest.connect() or not await guest.join_room():
            return False
        
        # Start heartbeats
        host_heartbeat = asyncio.create_task(host.start_heartbeat())
        guest_heartbeat = asyncio.create_task(guest.start_heartbeat())
        
        await asyncio.sleep(5)  # Let them establish connection
        
        # Simulate host network interruption (stop heartbeat)
        host_heartbeat.cancel()
        print("🔌 Simulating host network interruption...")
        
        # Wait for heartbeat timeout (should be around 45 seconds)
        await asyncio.sleep(50)
        
        # Check if guest received host disconnected event
        host_disconnected_events = [e for e in guest.events_received if e['event'] == 'host_disconnected']
        
        if len(host_disconnected_events) > 0:
            print("✅ Network interruption test passed - guest notified of host disconnect")
            return True
        else:
            print("❌ Network interruption test failed - no disconnect notification")
            return False
    
    finally:
        await host.disconnect()
        await guest.disconnect()

async def test_graceful_shutdown():
    """Test graceful shutdown during recording"""
    print("\n🧪 Testing graceful shutdown during recording...")
    
    host = SessionTestClient('http://localhost:8000', 'test-host-3', 'host')
    guest = SessionTestClient('http://localhost:8000', 'test-guest-2', 'guest')
    guest.room_id = host.room_id
    
    try:
        # Connect both clients
        if not await host.connect() or not await host.join_room():
            return False
        
        if not await guest.connect() or not await guest.join_room():
            return False
        
        # Start heartbeats
        host_heartbeat = asyncio.create_task(host.start_heartbeat())
        guest_heartbeat = asyncio.create_task(guest.start_heartbeat())
        
        await asyncio.sleep(2)
        
        # Start recording simulation in background
        recording_task = asyncio.create_task(host.simulate_recording(60))
        
        await asyncio.sleep(10)  # Let recording run for 10 seconds
        
        # Host leaves gracefully
        await host.graceful_leave()
        
        # Wait a bit and check if guest received notification
        await asyncio.sleep(2)
        
        host_disconnected_events = [e for e in guest.events_received if e['event'] == 'host_disconnected']
        
        if len(host_disconnected_events) > 0:
            print("✅ Graceful shutdown test passed - recording stopped gracefully")
            return True
        else:
            print("❌ Graceful shutdown test failed")
            return False
    
    finally:
        if 'recording_task' in locals():
            recording_task.cancel()
        if 'host_heartbeat' in locals():
            host_heartbeat.cancel()
        if 'guest_heartbeat' in locals():
            guest_heartbeat.cancel()
        await host.disconnect()
        await guest.disconnect()

async def test_server_stats():
    """Test server statistics endpoints"""
    print("\n🧪 Testing server statistics...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test health endpoint
            async with session.get('http://localhost:8000/health') as resp:
                if resp.status == 200:
                    health_data = await resp.json()
                    print(f"✅ Health check: {health_data['status']}")
                else:
                    print(f"❌ Health check failed: {resp.status}")
                    return False
            
            # Test API endpoints
            async with session.get('http://localhost:8000/api/health') as resp:
                if resp.status == 200:
                    api_health = await resp.json()
                    print(f"✅ API health: {api_health['status']}")
                    return True
                else:
                    print(f"❌ API health check failed: {resp.status}")
                    return False
    
    except Exception as e:
        print(f"❌ Server stats test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting Session Management Tests")
    print("=" * 50)
    
    tests = [
        ("Server Stats", test_server_stats),
        ("Basic Heartbeat", test_basic_heartbeat),
        ("Graceful Shutdown", test_graceful_shutdown),
        ("Network Interruption", test_network_interruption),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔄 Running {test_name}...")
        try:
            start_time = time.time()
            result = await test_func()
            duration = time.time() - start_time
            results[test_name] = {"passed": result, "duration": duration}
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status} - {test_name} ({duration:.1f}s)")
        except Exception as e:
            results[test_name] = {"passed": False, "error": str(e)}
            print(f"❌ FAILED - {test_name}: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for r in results.values() if r.get("passed", False))
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result.get("passed", False) else "❌"
        duration = result.get("duration", 0)
        error = result.get("error", "")
        print(f"{status} {test_name} ({duration:.1f}s) {error}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Session management is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the implementation.")

if __name__ == "__main__":
    asyncio.run(main()) 