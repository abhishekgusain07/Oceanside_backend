"""
Simple Socket.IO server for debugging
"""

import socketio
import logging

logger = logging.getLogger(__name__)

# Create a simple Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    logger=True,
    engineio_logger=True,
    async_mode='asgi'
)

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    await sio.emit('connected', {'status': 'connected'}, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")

@sio.event
async def test_event(sid, data):
    """Handle test event"""
    logger.info(f"Received test event from {sid}: {data}")
    await sio.emit('test_response', {'message': 'Hello from server'}, room=sid)

@sio.event
async def join_room(sid, room_id):
    """Handle room joining"""
    logger.info(f"Client {sid} joining room: {room_id}")
    await sio.enter_room(sid, room_id)
    await sio.emit('room-joined', {'roomId': room_id}, room=sid)
    await sio.emit('user-joined', sid, room=room_id, skip_sid=sid)

@sio.event
async def start_recording_request(sid, room_id):
    """Handle recording start request"""
    logger.info(f"Start recording requested by {sid} for room: {room_id}")
    # Emit to all clients in the room
    await sio.emit('start-recording', {'startTime': 0}, room=room_id)

@sio.event
async def recording_stopped(sid, data):
    """Handle recording stop notification"""
    room_id = data.get('roomId')
    user_id = data.get('userId')
    logger.info(f"Recording stopped by {sid} in room: {room_id}")
    # Emit to all clients in the room
    await sio.emit('stop-rec', {}, room=room_id)

@sio.event
async def host_leaving_room(sid, data):
    """Handle host leaving room"""
    room_id = data.get('roomId')
    logger.info(f"Host {sid} leaving room: {room_id}")
    await sio.emit('host_disconnected', {}, room=room_id, skip_sid=sid)
    await sio.leave_room(sid, room_id)

@sio.event
async def guest_leaving_room(sid, data):
    """Handle guest leaving room"""
    room_id = data.get('roomId')
    logger.info(f"Guest {sid} leaving room: {room_id}")
    await sio.emit('participant_left', {}, room=room_id, skip_sid=sid)
    await sio.leave_room(sid, room_id)

# WebRTC signaling events
@sio.event
async def offer(sid, data):
    """Handle WebRTC offer"""
    room_id = data.get('roomId')
    logger.info(f"WebRTC offer from {sid} in room: {room_id}")
    await sio.emit('offer', data, room=room_id, skip_sid=sid)

@sio.event
async def answer(sid, data):
    """Handle WebRTC answer"""
    room_id = data.get('roomId')
    logger.info(f"WebRTC answer from {sid} in room: {room_id}")
    await sio.emit('answer', data, room=room_id, skip_sid=sid)

@sio.event
async def ice_candidate(sid, data):
    """Handle ICE candidate"""
    room_id = data.get('roomId')
    logger.info(f"ICE candidate from {sid} in room: {room_id}")
    await sio.emit('ice-candidate', data, room=room_id, skip_sid=sid)

# Export the simple server
__all__ = ['sio'] 