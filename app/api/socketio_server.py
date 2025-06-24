"""
Socket.IO server for real-time signaling matching the Node.js project architecture.
"""
import socketio
import logging
from datetime import datetime
from typing import Dict, Optional
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.tasks.video_processing import process_video
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Socket.IO server instance
sio = socketio.AsyncServer(
    cors_allowed_origins="*",  # Configure based on your needs
    logger=True,
    async_mode='asgi',
    engineio_logger=True
)

# Store room participants for quick access
room_participants: Dict[str, Dict[str, Dict]] = {}  # room_id -> {participant_id: participant_info}

@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    logger.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {sid}")
    
    # Find and cleanup the participant from any rooms
    participant_room = None
    participant_id = None
    
    for room_id, participants in room_participants.items():
        for p_id, p_info in participants.items():
            if p_info.get('sid') == sid:
                participant_room = room_id
                participant_id = p_id
                break
        if participant_room:
            break
    
    if participant_room and participant_id:
        # Remove participant from room tracking
        if participant_id in room_participants[participant_room]:
            del room_participants[participant_room][participant_id]
        
        # Notify other participants
        await sio.emit('participant_left', {
            'participant_id': participant_id,
            'room_id': participant_room,
            'timestamp': datetime.utcnow().isoformat()
        }, room=participant_room, skip_sid=sid)
        
        # Clean up empty rooms
        if not room_participants[participant_room]:
            del room_participants[participant_room]

@sio.event
async def join_room(sid, room_id):
    """
    Handle join room requests - matches Node.js 'join-room' event.
    """
    try:
        if not room_id:
            logger.error(f"No room_id provided by {sid}")
            return
        
        # Join the Socket.IO room
        await sio.enter_room(sid, room_id)
        
        # Get room info to count clients
        room_info = sio.manager.get_participants(sio.namespace, room_id)
        num_clients = len(room_info) if room_info else 0
        
        logger.info(f"Socket {sid} joined room {room_id}. Clients in room: {num_clients}")
        
        if num_clients == 1:
            # First client - room creator (host)
            await sio.emit('room-created', room=sid)
        elif num_clients == 2:
            # Second client - joiner (guest)
            await sio.emit('room-joined', room=sid)
            await sio.emit('user-joined', sid, room=room_id, skip_sid=sid)
        else:
            logger.warning(f"Room {room_id} has {num_clients} clients, which may exceed max limit")
        
    except Exception as e:
        logger.error(f"Error in join-room: {str(e)}")

@sio.event
async def ready(sid, room_id):
    """Handle ready signal for WebRTC negotiation."""
    try:
        logger.info(f"Client {sid} ready in room {room_id}")
        await sio.emit('ready', room=room_id, skip_sid=sid)
    except Exception as e:
        logger.error(f"Error in ready event: {str(e)}")

@sio.event
async def offer(sid, data):
    """Handle WebRTC offer - matches Node.js implementation."""
    try:
        room_id = data.get('roomId')
        offer_data = data.get('offer')
        
        if not room_id or not offer_data:
            logger.error(f"Invalid offer data from {sid}")
            return
        
        logger.info(f"Forwarding offer from {sid} in room {room_id}")
        await sio.emit('offer', {
            'offer': offer_data,
            'roomId': room_id
        }, room=room_id, skip_sid=sid)
        
    except Exception as e:
        logger.error(f"Error handling offer: {str(e)}")

@sio.event
async def answer(sid, data):
    """Handle WebRTC answer - matches Node.js implementation."""
    try:
        room_id = data.get('roomId')
        answer_data = data.get('answer')
        
        if not room_id or not answer_data:
            logger.error(f"Invalid answer data from {sid}")
            return
        
        logger.info(f"Forwarding answer from {sid} in room {room_id}")
        await sio.emit('answer', {
            'answer': answer_data,
            'roomId': room_id
        }, room=room_id, skip_sid=sid)
        
    except Exception as e:
        logger.error(f"Error handling answer: {str(e)}")

@sio.event
async def ice_candidate(sid, data):
    """Handle ICE candidate - matches Node.js implementation."""
    try:
        room_id = data.get('roomId')
        candidate = data.get('candidate')
        
        if not room_id or not candidate:
            logger.error(f"Invalid ICE candidate data from {sid}")
            return
        
        logger.info(f"Forwarding ICE candidate from {sid} in room {room_id}")
        await sio.emit('ice-candidate', {
            'candidate': candidate
        }, room=room_id, skip_sid=sid)
        
    except Exception as e:
        logger.error(f"Error handling ICE candidate: {str(e)}")

@sio.event
async def start_recording_request(sid, room_id):
    """Handle recording start request - matches Node.js implementation."""
    try:
        if not room_id:
            logger.error(f"No room_id provided by {sid}")
            return
        
        # Calculate start time (5 seconds from now for countdown)
        start_time = int((datetime.utcnow().timestamp() + 5) * 1000)  # Convert to milliseconds
        
        logger.info(f"Starting recording for room {room_id} at {start_time}")
        await sio.emit('start-recording', {
            'startTime': start_time
        }, room=room_id)
        
    except Exception as e:
        logger.error(f"Error starting recording: {str(e)}")

@sio.event
async def recording_stopped(sid, data):
    """Handle recording stopped event - matches Node.js implementation."""
    try:
        room_id = data.get('roomId')
        user_id = data.get('userId')
        
        if not room_id:
            logger.error(f"No room_id provided by {sid}")
            return
        
        logger.info(f"Recording stopped for room {room_id} by user {user_id}")
        
        # Notify all participants to stop recording
        await sio.emit('stop-rec', room=room_id)
        
        # Schedule video processing task (with 10 second delay like in Node.js)
        async def schedule_processing():
            await asyncio.sleep(10)  # 10 second delay
            try:
                logger.info(f"Adding video processing job for room: {room_id}")
                task = process_video.delay(room_id=room_id, recording_id="", user_id=user_id)
                logger.info(f"Video processing task {task.id} scheduled for room: {room_id}")
            except Exception as e:
                logger.error(f"Error scheduling video processing for room {room_id}: {str(e)}")
                await sio.emit('video-processing-error', {
                    'error': str(e)
                }, room=room_id)
        
        # Schedule the processing task
        asyncio.create_task(schedule_processing())
        
    except Exception as e:
        logger.error(f"Error handling recording stopped: {str(e)}")

# Helper functions
def get_participant_id_by_sid(sid: str, room_id: str) -> Optional[str]:
    """Get participant ID by Socket.IO session ID."""
    if room_id not in room_participants:
        return None
    
    for participant_id, info in room_participants[room_id].items():
        if info.get('sid') == sid:
            return participant_id
    
    return None

def get_sid_by_participant_id(participant_id: str, room_id: str) -> Optional[str]:
    """Get Socket.IO session ID by participant ID."""
    if room_id not in room_participants:
        return None
    
    participant_info = room_participants[room_id].get(participant_id)
    return participant_info.get('sid') if participant_info else None

def get_room_stats(room_id: str) -> Dict:
    """Get statistics for a room."""
    if room_id not in room_participants:
        return {'participant_count': 0, 'participants': []}
    
    participants = []
    for participant_id, info in room_participants[room_id].items():
        participants.append({
            'participant_id': participant_id,
            'user_type': info.get('user_type'),
            'joined_at': info.get('joined_at')
        })
    
    return {
        'participant_count': len(participants),
        'participants': participants
    }

# Utility function to get connection stats
def get_connection_stats():
    """Get current connection statistics."""
    room_counts = {}
    
    # Get room information from Socket.IO manager
    try:
        if hasattr(sio.manager, 'rooms') and sio.namespace in sio.manager.rooms:
            rooms = sio.manager.rooms[sio.namespace]
            for room_id, room_sids in rooms.items():
                if room_id != '/':  # Skip default room
                    room_counts[room_id] = len(room_sids)
    except Exception as e:
        logger.error(f"Error getting room stats: {str(e)}")
    
    total_connections = 0
    try:
        default_room_sids = sio.manager.get_participants(sio.namespace, '/')
        total_connections = len(default_room_sids) if default_room_sids else 0
    except Exception as e:
        logger.error(f"Error getting connection count: {str(e)}")
    
    return {
        "total_connections": total_connections,
        "active_rooms": len(room_counts),
        "room_details": room_counts
    }

# Export the Socket.IO server instance
__all__ = ['sio'] 