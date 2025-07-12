"""
Unit tests for Socket.IO functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from app.api.simple_socketio import sio

class MockSocket:
    """Mock Socket.IO instance for testing."""
    
    def __init__(self):
        self.events = {}
        self.rooms = {}
        self.emissions = []
        
    async def emit(self, event, data=None, room=None, skip_sid=None):
        """Mock emit method."""
        self.emissions.append({
            'event': event,
            'data': data,
            'room': room,
            'skip_sid': skip_sid
        })
        
    async def enter_room(self, sid, room):
        """Mock enter_room method."""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(sid)
        
    async def leave_room(self, sid, room):
        """Mock leave_room method."""
        if room in self.rooms:
            self.rooms[room].discard(sid)
            if not self.rooms[room]:
                del self.rooms[room]

@pytest.fixture
def mock_sio():
    """Create a mock Socket.IO instance."""
    return MockSocket()

class TestSocketIOEvents:
    """Test Socket.IO event handlers."""
    
    @pytest.mark.asyncio
    async def test_connect_event(self, mock_sio):
        """Test client connection event."""
        with patch.object(sio, 'emit', new=mock_sio.emit):
            # Import the event handler
            from app.api.simple_socketio import connect
            
            # Test connection
            await connect('test-sid', {})
            
            # Verify connected event was emitted
            assert len(mock_sio.emissions) == 1
            emission = mock_sio.emissions[0]
            assert emission['event'] == 'connected'
            assert emission['data'] == {'status': 'connected'}
            assert emission['room'] == 'test-sid'
    
    @pytest.mark.asyncio
    async def test_join_room_event(self, mock_sio):
        """Test room joining event."""
        with patch.object(sio, 'emit', new=mock_sio.emit), \
             patch.object(sio, 'enter_room', new=mock_sio.enter_room):
            
            from app.api.simple_socketio import join_room
            
            # Test joining room
            await join_room('test-sid', 'room-123')
            
            # Verify room was joined
            assert 'room-123' in mock_sio.rooms
            assert 'test-sid' in mock_sio.rooms['room-123']
            
            # Verify events were emitted
            assert len(mock_sio.emissions) == 2
            
            # Check room-joined event
            room_joined = mock_sio.emissions[0]
            assert room_joined['event'] == 'room-joined'
            assert room_joined['data'] == {'roomId': 'room-123'}
            assert room_joined['room'] == 'test-sid'
            
            # Check user-joined event
            user_joined = mock_sio.emissions[1]
            assert user_joined['event'] == 'user-joined'
            assert user_joined['room'] == 'room-123'
            assert user_joined['skip_sid'] == 'test-sid'
    
    @pytest.mark.asyncio
    async def test_start_recording_request(self, mock_sio):
        """Test recording start request event."""
        with patch.object(sio, 'emit', new=mock_sio.emit):
            from app.api.simple_socketio import start_recording_request
            
            # Test start recording request
            await start_recording_request('test-sid', 'room-123')
            
            # Verify start-recording event was emitted
            assert len(mock_sio.emissions) == 1
            emission = mock_sio.emissions[0]
            assert emission['event'] == 'start-recording'
            assert emission['data'] == {'startTime': 0}
            assert emission['room'] == 'room-123'
    
    @pytest.mark.asyncio
    async def test_recording_stopped(self, mock_sio):
        """Test recording stopped event."""
        with patch.object(sio, 'emit', new=mock_sio.emit):
            from app.api.simple_socketio import recording_stopped
            
            # Test recording stopped
            data = {'roomId': 'room-123', 'userId': 'user-456'}
            await recording_stopped('test-sid', data)
            
            # Verify stop-rec event was emitted
            assert len(mock_sio.emissions) == 1
            emission = mock_sio.emissions[0]
            assert emission['event'] == 'stop-rec'
            assert emission['data'] == {}
            assert emission['room'] == 'room-123'
    
    @pytest.mark.asyncio
    async def test_host_leaving_room(self, mock_sio):
        """Test host leaving room event."""
        with patch.object(sio, 'emit', new=mock_sio.emit), \
             patch.object(sio, 'leave_room', new=mock_sio.leave_room):
            
            from app.api.simple_socketio import host_leaving_room
            
            # Setup room with host
            await mock_sio.enter_room('test-sid', 'room-123')
            
            # Test host leaving
            data = {'roomId': 'room-123', 'userId': 'user-456'}
            await host_leaving_room('test-sid', data)
            
            # Verify host_disconnected event was emitted
            assert len(mock_sio.emissions) == 1
            emission = mock_sio.emissions[0]
            assert emission['event'] == 'host_disconnected'
            assert emission['room'] == 'room-123'
            assert emission['skip_sid'] == 'test-sid'
            
            # Verify host left the room
            assert 'room-123' not in mock_sio.rooms or 'test-sid' not in mock_sio.rooms.get('room-123', set())
    
    @pytest.mark.asyncio
    async def test_guest_leaving_room(self, mock_sio):
        """Test guest leaving room event."""
        with patch.object(sio, 'emit', new=mock_sio.emit), \
             patch.object(sio, 'leave_room', new=mock_sio.leave_room):
            
            from app.api.simple_socketio import guest_leaving_room
            
            # Setup room with guest
            await mock_sio.enter_room('test-sid', 'room-123')
            
            # Test guest leaving
            data = {'roomId': 'room-123', 'userId': 'user-456'}
            await guest_leaving_room('test-sid', data)
            
            # Verify participant_left event was emitted
            assert len(mock_sio.emissions) == 1
            emission = mock_sio.emissions[0]
            assert emission['event'] == 'participant_left'
            assert emission['room'] == 'room-123'
            assert emission['skip_sid'] == 'test-sid'
    
    @pytest.mark.asyncio
    async def test_webrtc_offer(self, mock_sio):
        """Test WebRTC offer event."""
        with patch.object(sio, 'emit', new=mock_sio.emit):
            from app.api.simple_socketio import offer
            
            # Test WebRTC offer
            data = {
                'roomId': 'room-123',
                'offer': {
                    'type': 'offer',
                    'sdp': 'mock-sdp-data'
                }
            }
            await offer('test-sid', data)
            
            # Verify offer event was forwarded
            assert len(mock_sio.emissions) == 1
            emission = mock_sio.emissions[0]
            assert emission['event'] == 'offer'
            assert emission['data'] == data
            assert emission['room'] == 'room-123'
            assert emission['skip_sid'] == 'test-sid'
    
    @pytest.mark.asyncio
    async def test_webrtc_answer(self, mock_sio):
        """Test WebRTC answer event."""
        with patch.object(sio, 'emit', new=mock_sio.emit):
            from app.api.simple_socketio import answer
            
            # Test WebRTC answer
            data = {
                'roomId': 'room-123',
                'answer': {
                    'type': 'answer',
                    'sdp': 'mock-sdp-data'
                }
            }
            await answer('test-sid', data)
            
            # Verify answer event was forwarded
            assert len(mock_sio.emissions) == 1
            emission = mock_sio.emissions[0]
            assert emission['event'] == 'answer'
            assert emission['data'] == data
            assert emission['room'] == 'room-123'
            assert emission['skip_sid'] == 'test-sid'
    
    @pytest.mark.asyncio
    async def test_webrtc_ice_candidate(self, mock_sio):
        """Test WebRTC ICE candidate event."""
        with patch.object(sio, 'emit', new=mock_sio.emit):
            from app.api.simple_socketio import ice_candidate
            
            # Test ICE candidate
            data = {
                'roomId': 'room-123',
                'candidate': {
                    'candidate': 'candidate:1 1 UDP 2122260223 192.168.1.100 54400 typ host',
                    'sdpMid': '0',
                    'sdpMLineIndex': 0
                }
            }
            await ice_candidate('test-sid', data)
            
            # Verify ice-candidate event was forwarded
            assert len(mock_sio.emissions) == 1
            emission = mock_sio.emissions[0]
            assert emission['event'] == 'ice-candidate'
            assert emission['data'] == data
            assert emission['room'] == 'room-123'
            assert emission['skip_sid'] == 'test-sid'

class TestSocketIOIntegration:
    """Test Socket.IO integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_recording_workflow(self, mock_sio):
        """Test complete recording workflow through Socket.IO."""
        with patch.object(sio, 'emit', new=mock_sio.emit), \
             patch.object(sio, 'enter_room', new=mock_sio.enter_room), \
             patch.object(sio, 'leave_room', new=mock_sio.leave_room):
            
            from app.api.simple_socketio import (
                join_room, start_recording_request, recording_stopped, host_leaving_room
            )
            
            # 1. Host joins room
            await join_room('host-sid', 'room-123')
            assert 'host-sid' in mock_sio.rooms['room-123']
            
            # 2. Start recording
            await start_recording_request('host-sid', 'room-123')
            start_emission = next(e for e in mock_sio.emissions if e['event'] == 'start-recording')
            assert start_emission['room'] == 'room-123'
            
            # 3. Stop recording
            await recording_stopped('host-sid', {'roomId': 'room-123', 'userId': 'host-user'})
            stop_emission = next(e for e in mock_sio.emissions if e['event'] == 'stop-rec')
            assert stop_emission['room'] == 'room-123'
            
            # 4. Host leaves
            await host_leaving_room('host-sid', {'roomId': 'room-123', 'userId': 'host-user'})
            disconnect_emission = next(e for e in mock_sio.emissions if e['event'] == 'host_disconnected')
            assert disconnect_emission['room'] == 'room-123'
    
    @pytest.mark.asyncio
    async def test_multi_participant_scenario(self, mock_sio):
        """Test scenario with multiple participants."""
        with patch.object(sio, 'emit', new=mock_sio.emit), \
             patch.object(sio, 'enter_room', new=mock_sio.enter_room), \
             patch.object(sio, 'leave_room', new=mock_sio.leave_room):
            
            from app.api.simple_socketio import join_room, guest_leaving_room
            
            # Host and guest join
            await join_room('host-sid', 'room-123')
            await join_room('guest-sid', 'room-123')
            
            # Verify both are in the room
            assert 'host-sid' in mock_sio.rooms['room-123']
            assert 'guest-sid' in mock_sio.rooms['room-123']
            assert len(mock_sio.rooms['room-123']) == 2
            
            # Guest leaves
            await guest_leaving_room('guest-sid', {'roomId': 'room-123', 'userId': 'guest-user'})
            
            # Verify guest left but host remains
            assert 'guest-sid' not in mock_sio.rooms['room-123']
            assert 'host-sid' in mock_sio.rooms['room-123']
            assert len(mock_sio.rooms['room-123']) == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])