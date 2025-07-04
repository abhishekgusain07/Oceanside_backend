"""
Simple Socket.IO server for debugging
"""

import socketio
import logging

logger = logging.getLogger(__name__)

# Create a simple Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
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

# Export the simple server
__all__ = ['sio'] 