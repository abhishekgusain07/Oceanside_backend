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
    """Handle recording stop notification and trigger video processing"""
    room_id = data.get('roomId')
    user_id = data.get('userId', 'unknown')
    logger.info(f"Recording stopped by {sid} in room: {room_id}, user: {user_id}")
    
    # Emit to all clients in the room
    await sio.emit('stop-rec', {}, room=room_id)
    
    # Trigger video processing via Celery
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.recording_service import RecordingService
        
        # Use the recording service helper method
        async with AsyncSessionLocal() as db:
            service = RecordingService(db)
            task_id = await service.trigger_video_processing(room_id, user_id)
            
            if task_id:
                logger.info(f"🎬 Video processing task queued with ID: {task_id}")
                
                # Emit processing status to clients
                await sio.emit('video-processing-started', {
                    'room_id': room_id,
                    'task_id': task_id,
                    'status': 'processing'
                }, room=room_id)
                
            else:
                logger.error(f"❌ Failed to trigger video processing for room {room_id}")
                await sio.emit('video-processing-error', {
                    'room_id': room_id,
                    'error': 'Failed to start video processing'
                }, room=room_id)
                
    except Exception as e:
        logger.error(f"❌ Exception while triggering video processing for room {room_id}: {str(e)}")
        await sio.emit('video-processing-error', {
            'room_id': room_id,
            'error': f'Video processing error: {str(e)}'
        }, room=room_id)

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

# Additional events for video processing status updates
@sio.event 
async def request_processing_status(sid, data):
    """Handle request for processing status"""
    room_id = data.get('roomId')
    logger.info(f"Processing status requested for room {room_id} by {sid}")
    
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.recording_service import RecordingService
        
        async with AsyncSessionLocal() as db:
            service = RecordingService(db)
            recording = await service.get_recording_by_room_id(room_id)
            
            if recording:
                await sio.emit('processing-status-response', {
                    'room_id': room_id,
                    'status': recording.status.value,
                    'video_url': recording.video_url,
                    'processing_attempts': recording.processing_attempts,
                    'processed_at': recording.processed_at.isoformat() if recording.processed_at else None,
                    'error': recording.processing_error
                }, room=sid)
            else:
                await sio.emit('processing-status-response', {
                    'room_id': room_id,
                    'error': 'Recording not found'
                }, room=sid)
                
    except Exception as e:
        logger.error(f"Error getting processing status for room {room_id}: {str(e)}")
        await sio.emit('processing-status-response', {
            'room_id': room_id,
            'error': str(e)
        }, room=sid)

# Utility function to emit processing updates from Celery tasks
async def emit_processing_update(room_id: str, status: str, video_url: str = None, error: str = None):
    """
    Emit processing status updates to all clients in a room.
    This can be called from Celery tasks or other parts of the system.
    """
    try:
        update_data = {
            'room_id': room_id,
            'status': status
        }
        
        if video_url:
            update_data['video_url'] = video_url
        if error:
            update_data['error'] = error
            
        await sio.emit('video-processing-update', update_data, room=room_id)
        logger.info(f"Emitted processing update for room {room_id}: {status}")
        
    except Exception as e:
        logger.error(f"Failed to emit processing update for room {room_id}: {str(e)}")

# Export the simple server and utility functions
__all__ = ['sio', 'emit_processing_update'] 