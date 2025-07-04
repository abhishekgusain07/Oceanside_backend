"""
Enhanced Socket.IO server with robust session management
Handles heartbeats, network interruptions, and graceful shutdowns
"""

import socketio
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
from dataclasses import dataclass
import json


logger = logging.getLogger(__name__)

@dataclass
class SessionInfo:
    user_id: str
    user_type: str  # 'host' | 'guest'
    room_id: str
    last_heartbeat: datetime
    is_recording: bool
    socket_id: str
    connection_time: datetime

class EnhancedSocketIOServer:
    def __init__(self):
        self.sio = socketio.AsyncServer(
            cors_allowed_origins="*",
            logger=True,
            engineio_logger=True,
            ping_timeout=60,
            ping_interval=25
        )
        
        # Session tracking
        self.sessions: Dict[str, SessionInfo] = {}  # socket_id -> SessionInfo
        self.rooms: Dict[str, Set[str]] = {}  # room_id -> set of socket_ids
        self.heartbeat_timeout = 45  # seconds
        
        # Schedule heartbeat monitoring to start later
        self._heartbeat_task = None
        
        self.setup_event_handlers()

    def setup_event_handlers(self):
        """Setup all socket event handlers"""
        
        @self.sio.event
        async def connect(sid, environ):
            logger.info(f"Client connected: {sid}")
            
            # Start heartbeat monitor if not running
            if self._heartbeat_task is None:
                try:
                    self._heartbeat_task = asyncio.create_task(self.heartbeat_monitor())
                    logger.info("✅ Heartbeat monitor started on first connection")
                except Exception as e:
                    logger.error(f"Failed to start heartbeat monitor: {e}")
            
            await self.sio.emit('connected', {'status': 'connected'}, room=sid)

        @self.sio.event
        async def disconnect(sid):
            logger.info(f"Client disconnected: {sid}")
            await self.handle_disconnect(sid, 'client_disconnect')

        @self.sio.event
        async def join_room(sid, room_id):
            """Join a room and register session"""
            logger.info(f"Client {sid} joining room {room_id}")
            await self.sio.enter_room(sid, room_id)
            
            # Initialize room if it doesn't exist
            if room_id not in self.rooms:
                self.rooms[room_id] = set()
            
            self.rooms[room_id].add(sid)
            
            # Notify others in the room
            await self.sio.emit('user_joined', {'socket_id': sid}, room=room_id, skip_sid=sid)
            await self.sio.emit('room_joined', room=sid)

        @self.sio.event
        async def heartbeat(sid, data):
            """Handle heartbeat from client"""
            room_id = data.get('roomId')
            user_id = data.get('userId')
            user_type = data.get('userType', 'guest')
            is_recording = data.get('isRecording', False)
            
            # Update or create session info
            self.sessions[sid] = SessionInfo(
                user_id=user_id,
                user_type=user_type,
                room_id=room_id,
                last_heartbeat=datetime.now(),
                is_recording=is_recording,
                socket_id=sid,
                connection_time=self.sessions.get(sid, SessionInfo(
                    user_id=user_id,
                    user_type=user_type,
                    room_id=room_id,
                    last_heartbeat=datetime.now(),
                    is_recording=is_recording,
                    socket_id=sid,
                    connection_time=datetime.now()
                )).connection_time
            )
            
            # Send heartbeat response
            await self.sio.emit('heartbeat_response', {
                'timestamp': datetime.now().timestamp() * 1000,
                'status': 'healthy'
            }, room=sid)
            
            logger.debug(f"Heartbeat from {user_type} {user_id} in room {room_id}")

        @self.sio.event
        async def host_leaving_room(sid, data):
            """Handle host leaving room gracefully"""
            room_id = data.get('roomId')
            user_id = data.get('userId')
            reason = data.get('reason', 'user_exit')
            
            logger.info(f"Host {user_id} leaving room {room_id} (reason: {reason})")
            
            # Notify all guests that host is leaving
            await self.sio.emit('host_disconnected', {
                'reason': reason,
                'message': 'Host has left the session'
            }, room=room_id, skip_sid=sid)
            
            # Clean up the room
            await self.cleanup_room(room_id, sid)

        @self.sio.event
        async def guest_leaving_room(sid, data):
            """Handle guest leaving room gracefully"""
            room_id = data.get('roomId')
            user_id = data.get('userId')
            reason = data.get('reason', 'user_exit')
            
            logger.info(f"Guest {user_id} leaving room {room_id} (reason: {reason})")
            
            # Notify host that guest left
            await self.sio.emit('guest_left', {
                'guestId': user_id,
                'reason': reason
            }, room=room_id, skip_sid=sid)
            
            # Remove from session tracking
            await self.remove_session(sid)

        @self.sio.event
        async def recording_verification_response(sid, data):
            """Handle recording verification response from host"""
            room_id = data.get('roomId')
            actual_chunks = data.get('actualChunks', 0)
            uploaded_chunks = data.get('uploadedChunks', 0)
            failed_chunks = data.get('failedChunks', 0)
            expected_chunks = data.get('expectedChunks', 0)
            
            logger.info(f"Recording verification for room {room_id}: "
                       f"{uploaded_chunks}/{actual_chunks} chunks uploaded, "
                       f"{failed_chunks} failed, {expected_chunks} expected")
            
            # You could store this verification data or trigger alerts if mismatched
            if uploaded_chunks < expected_chunks:
                logger.warning(f"Recording incomplete: missing {expected_chunks - uploaded_chunks} chunks")

        # WebRTC signaling events (existing functionality)
        @self.sio.event
        async def offer(sid, data):
            """Forward WebRTC offer"""
            room_id = await self.get_room_for_socket(sid)
            if room_id:
                await self.sio.emit('offer', data, room=room_id, skip_sid=sid)

        @self.sio.event
        async def answer(sid, data):
            """Forward WebRTC answer"""
            room_id = await self.get_room_for_socket(sid)
            if room_id:
                await self.sio.emit('answer', data, room=room_id, skip_sid=sid)

        @self.sio.event
        async def ice_candidate(sid, data):
            """Forward ICE candidate"""
            room_id = await self.get_room_for_socket(sid)
            if room_id:
                await self.sio.emit('ice-candidate', data, room=room_id, skip_sid=sid)

        @self.sio.event
        async def start_recording(sid, data):
            """Start recording signal"""
            room_id = await self.get_room_for_socket(sid)
            if room_id:
                start_time = datetime.now().timestamp() * 1000
                await self.sio.emit('start-recording', {'startTime': start_time}, room=room_id)

        @self.sio.event
        async def stop_recording(sid, data):
            """Stop recording signal"""
            room_id = await self.get_room_for_socket(sid)
            if room_id:
                await self.sio.emit('stop-rec', room=room_id)

    async def heartbeat_monitor(self):
        """Monitor heartbeats and detect disconnected clients"""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            now = datetime.now()
            expired_sessions = []
            
            for sid, session in self.sessions.items():
                time_since_heartbeat = (now - session.last_heartbeat).total_seconds()
                
                if time_since_heartbeat > self.heartbeat_timeout:
                    logger.warning(f"Session {sid} heartbeat timeout: {time_since_heartbeat}s")
                    expired_sessions.append(sid)
            
            # Handle expired sessions
            for sid in expired_sessions:
                await self.handle_disconnect(sid, 'heartbeat_timeout')

    async def handle_disconnect(self, sid: str, reason: str):
        """Handle client disconnection with proper cleanup"""
        if sid in self.sessions:
            session = self.sessions[sid]
            
            logger.info(f"Handling disconnect for {session.user_type} {session.user_id} "
                       f"in room {session.room_id} (reason: {reason})")
            
            # If it's a host disconnecting, notify guests
            if session.user_type == 'host':
                await self.sio.emit('host_disconnected', {
                    'reason': reason,
                    'message': 'Host connection lost'
                }, room=session.room_id, skip_sid=sid)
                
                # Clean up the entire room
                await self.cleanup_room(session.room_id, sid)
            else:
                # Guest disconnecting, notify host
                await self.sio.emit('guest_left', {
                    'guestId': session.user_id,
                    'reason': 'network_timeout' if reason == 'heartbeat_timeout' else reason
                }, room=session.room_id, skip_sid=sid)
            
            # Remove from session tracking
            await self.remove_session(sid)

    async def cleanup_room(self, room_id: str, host_sid: str):
        """Clean up a room when host leaves"""
        if room_id in self.rooms:
            # Get all participants
            participants = self.rooms[room_id].copy()
            
            # Remove all participants from the room
            for participant_sid in participants:
                await self.sio.leave_room(participant_sid, room_id)
                if participant_sid in self.sessions:
                    del self.sessions[participant_sid]
            
            # Remove room from tracking
            del self.rooms[room_id]
            
            logger.info(f"Cleaned up room {room_id} with {len(participants)} participants")

    async def remove_session(self, sid: str):
        """Remove a session from tracking"""
        if sid in self.sessions:
            session = self.sessions[sid]
            
            # Remove from room tracking
            if session.room_id in self.rooms:
                self.rooms[session.room_id].discard(sid)
                
                # If room is empty, remove it
                if not self.rooms[session.room_id]:
                    del self.rooms[session.room_id]
            
            # Remove from session tracking
            del self.sessions[sid]
            
            await self.sio.leave_room(sid, session.room_id)

    async def get_room_for_socket(self, sid: str) -> Optional[str]:
        """Get the room ID for a socket"""
        if sid in self.sessions:
            return self.sessions[sid].room_id
        return None

    async def request_recording_verification(self, room_id: str, expected_chunks: int):
        """Request recording verification from host"""
        await self.sio.emit('recording_verification_request', {
            'expectedChunks': expected_chunks
        }, room=room_id)

    def get_app(self):
        """Get the Socket.IO app for integration with FastAPI"""
        return self.sio
    
    def start_heartbeat_monitor(self):
        """Start the heartbeat monitoring task"""
        if self._heartbeat_task is None:
            try:
                loop = asyncio.get_running_loop()
                self._heartbeat_task = loop.create_task(self.heartbeat_monitor())
            except RuntimeError:
                # No running loop yet, start it lazily
                logger.info("No running event loop found, heartbeat monitor will start on first connection")
    
    async def stop_heartbeat_monitor(self):
        """Stop the heartbeat monitoring task"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

# Create global instance
enhanced_socketio_server = EnhancedSocketIOServer()
sio = enhanced_socketio_server.get_app()

# Utility functions for backward compatibility with existing code
def get_room_stats(room_id: str) -> Dict:
    """Get statistics for a room using the enhanced session manager."""
    room_sessions = [s for s in enhanced_socketio_server.sessions.values() if s.room_id == room_id]
    return {
        'room_id': room_id,
        'participant_count': len(room_sessions),
        'participants': [
            {
                'user_id': s.user_id,
                'user_type': s.user_type,
                'is_recording': s.is_recording,
                'connection_time': s.connection_time.isoformat(),
                'last_heartbeat': s.last_heartbeat.isoformat()
            }
            for s in room_sessions
        ]
    }

def get_connection_stats():
    """Get overall connection statistics using the enhanced session manager."""
    total_sessions = len(enhanced_socketio_server.sessions)
    rooms = {}
    
    for session in enhanced_socketio_server.sessions.values():
        room_id = session.room_id
        if room_id not in rooms:
            rooms[room_id] = {
                'participant_count': 0,
                'recording_sessions': 0
            }
        rooms[room_id]['participant_count'] += 1
        if session.is_recording:
            rooms[room_id]['recording_sessions'] += 1
    
    return {
        'total_rooms': len(enhanced_socketio_server.rooms),
        'total_participants': total_sessions,
        'room_details': rooms,
        'active_recordings': sum(1 for s in enhanced_socketio_server.sessions.values() if s.is_recording)
    }

def get_participant_id_by_sid(sid: str, room_id: str) -> Optional[str]:
    """Get participant ID by Socket.IO session ID."""
    session = enhanced_socketio_server.sessions.get(sid)
    if session and session.room_id == room_id:
        return session.user_id
    return None

def get_sid_by_participant_id(participant_id: str, room_id: str) -> Optional[str]:
    """Get Socket.IO session ID by participant ID."""
    for sid, session in enhanced_socketio_server.sessions.items():
        if session.user_id == participant_id and session.room_id == room_id:
            return sid
    return None

# Export the Socket.IO server instance
__all__ = ['sio', 'enhanced_socketio_server'] 