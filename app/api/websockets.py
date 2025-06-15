"""
Improved WebSocket signaling endpoint for real-time communication during recording sessions.
"""
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Set
import json
import logging
import asyncio
import time
from datetime import datetime
from enum import Enum
import uuid

from app.core.database import get_db
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)

class MessageType(str, Enum):
    """WebSocket message types for type safety."""
    WEBRTC_OFFER = "webrtc_offer"
    WEBRTC_ANSWER = "webrtc_answer"
    ICE_CANDIDATE = "ice_candidate"
    RECORDING_STATUS = "recording_status"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

class ParticipantConnection:
    """Represents a participant's WebSocket connection with metadata."""
    
    def __init__(self, websocket: WebSocket, participant_id: str, session_id: str):
        self.websocket = websocket
        self.participant_id = participant_id
        self.session_id = session_id
        self.connected_at = datetime.utcnow()
        self.last_heartbeat = time.time()
        self.connection_id = str(uuid.uuid4())
    
    async def send_message(self, message: dict) -> bool:
        """
        Send message to this participant with error handling.
        
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            await self.websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to participant {self.participant_id}: {e}")
            return False
    
    def update_heartbeat(self):
        """Update the last heartbeat timestamp."""
        self.last_heartbeat = time.time()
    
    def is_stale(self, timeout: int = 60) -> bool:
        """Check if connection is stale based on heartbeat."""
        return time.time() - self.last_heartbeat > timeout

class WebSocketConnectionManager:
    """
    Enhanced WebSocket connection manager with proper error handling and cleanup.
    """
    
    def __init__(self, max_connections_per_session: int = 10):
        # Store connections by session_id -> set of ParticipantConnection
        self.sessions: Dict[str, Set[ParticipantConnection]] = {}
        # Quick lookup by connection_id
        self.connections: Dict[str, ParticipantConnection] = {}
        self.max_connections_per_session = max_connections_per_session
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background task to clean up stale connections."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
    
    async def _cleanup_stale_connections(self):
        """Background task to clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                stale_connections = []
                
                for connection in self.connections.values():
                    if connection.is_stale():
                        stale_connections.append(connection)
                
                for connection in stale_connections:
                    logger.info(f"Cleaning up stale connection: {connection.connection_id}")
                    await self._disconnect_internal(connection)
                    
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def connect(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        participant_id: str,
        db: AsyncSession
    ) -> ParticipantConnection:
        """
        Add a new WebSocket connection to a specific session.
        
        Args:
            websocket: The WebSocket connection
            session_id: Unique identifier for the session
            participant_id: Unique identifier for the participant
            db: Database session for validation
            
        Returns:
            ParticipantConnection: The created connection object
            
        Raises:
            HTTPException: If session doesn't exist or connection limit exceeded
        """
        # Validate session exists
        service = SessionService(db)
        session = await service.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check connection limits
        if session_id in self.sessions:
            if len(self.sessions[session_id]) >= self.max_connections_per_session:
                raise HTTPException(
                    status_code=429, 
                    detail="Session connection limit exceeded"
                )
        
        # Accept the WebSocket connection
        await websocket.accept()
        
        # Create participant connection
        connection = ParticipantConnection(websocket, participant_id, session_id)
        
        # Add to tracking structures
        if session_id not in self.sessions:
            self.sessions[session_id] = set()
        
        self.sessions[session_id].add(connection)
        self.connections[connection.connection_id] = connection
        
        logger.info(
            f"WebSocket connected: session={session_id}, "
            f"participant={participant_id}, connection={connection.connection_id}"
        )
        
        # Notify other participants
        await self.broadcast(
            session_id,
            {
                "type": MessageType.PARTICIPANT_JOINED,
                "participant_id": participant_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            exclude_connection=connection
        )
        
        return connection
    
    async def disconnect(self, connection: ParticipantConnection):
        """
        Remove a WebSocket connection from a session.
        
        Args:
            connection: The connection to remove
        """
        await self._disconnect_internal(connection)
        
        # Notify other participants
        await self.broadcast(
            connection.session_id,
            {
                "type": MessageType.PARTICIPANT_LEFT,
                "participant_id": connection.participant_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def _disconnect_internal(self, connection: ParticipantConnection):
        """Internal disconnect method without broadcasting."""
        session_id = connection.session_id
        
        # Remove from tracking structures
        if session_id in self.sessions:
            self.sessions[session_id].discard(connection)
            if not self.sessions[session_id]:  # Remove empty session
                del self.sessions[session_id]
        
        if connection.connection_id in self.connections:
            del self.connections[connection.connection_id]
        
        # Close WebSocket if still open
        try:
            await connection.websocket.close()
        except Exception:
            pass  # Connection might already be closed
        
        logger.info(
            f"WebSocket disconnected: session={session_id}, "
            f"participant={connection.participant_id}, connection={connection.connection_id}"
        )
    
    async def broadcast(
        self, 
        session_id: str, 
        message: dict, 
        exclude_connection: Optional[ParticipantConnection] = None,
        target_participant: Optional[str] = None
    ):
        """
        Broadcast a message to participants in a session.
        
        Args:
            session_id: Session to broadcast to
            message: Message to send
            exclude_connection: Connection to exclude from broadcast
            target_participant: If specified, only send to this participant
        """
        if session_id not in self.sessions:
            return
        
        connections = self.sessions[session_id].copy()  # Copy to avoid modification during iteration
        failed_connections = []
        
        for connection in connections:
            # Skip excluded connection
            if exclude_connection and connection == exclude_connection:
                continue
            
            # Skip if targeting specific participant
            if target_participant and connection.participant_id != target_participant:
                continue
            
            # Try to send message
            success = await connection.send_message(message)
            if not success:
                failed_connections.append(connection)
        
        # Clean up failed connections
        for failed_connection in failed_connections:
            await self._disconnect_internal(failed_connection)
    
    async def handle_signaling_message(
        self, 
        connection: ParticipantConnection,
        message: dict, 
        db: AsyncSession
    ):
        """
        Handle different types of signaling messages with improved validation.
        
        Args:
            connection: The participant connection
            message: Parsed WebSocket message
            db: Database session
        """
        try:
            message_type = message.get('type')
            if not message_type:
                await connection.send_message({
                    'type': MessageType.ERROR,
                    'detail': 'Message type is required'
                })
                return
            
            # Update heartbeat
            connection.update_heartbeat()
            
            # Handle different message types
            if message_type == MessageType.WEBRTC_OFFER:
                await self._handle_webrtc_offer(connection, message)
            
            elif message_type == MessageType.WEBRTC_ANSWER:
                await self._handle_webrtc_answer(connection, message)
            
            elif message_type == MessageType.ICE_CANDIDATE:
                await self._handle_ice_candidate(connection, message)
            
            elif message_type == MessageType.RECORDING_STATUS:
                await self._handle_recording_status(connection, message)
            
            elif message_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(connection, message)
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await connection.send_message({
                    'type': MessageType.ERROR,
                    'detail': f'Unknown message type: {message_type}'
                })
        
        except Exception as e:
            logger.error(f"Error handling signaling message: {e}", exc_info=True)
            await connection.send_message({
                'type': MessageType.ERROR,
                'detail': 'Internal server error'
            })
    
    async def _handle_webrtc_offer(self, connection: ParticipantConnection, message: dict):
        """Handle WebRTC offer message."""
        target_participant = message.get('target_participant')
        offer = message.get('offer')
        
        if not offer:
            await connection.send_message({
                'type': MessageType.ERROR,
                'detail': 'Offer is required'
            })
            return
        
        await self.broadcast(
            connection.session_id,
            {
                'type': MessageType.WEBRTC_OFFER,
                'sender_id': connection.participant_id,
                'offer': offer,
                'timestamp': datetime.utcnow().isoformat()
            },
            exclude_connection=connection,
            target_participant=target_participant
        )
    
    async def _handle_webrtc_answer(self, connection: ParticipantConnection, message: dict):
        """Handle WebRTC answer message."""
        target_participant = message.get('target_participant')
        answer = message.get('answer')
        
        if not answer:
            await connection.send_message({
                'type': MessageType.ERROR,
                'detail': 'Answer is required'
            })
            return
        
        await self.broadcast(
            connection.session_id,
            {
                'type': MessageType.WEBRTC_ANSWER,
                'sender_id': connection.participant_id,
                'answer': answer,
                'timestamp': datetime.utcnow().isoformat()
            },
            exclude_connection=connection,
            target_participant=target_participant
        )
    
    async def _handle_ice_candidate(self, connection: ParticipantConnection, message: dict):
        """Handle ICE candidate message."""
        target_participant = message.get('target_participant')
        candidate = message.get('candidate')
        
        if not candidate:
            await connection.send_message({
                'type': MessageType.ERROR,
                'detail': 'Candidate is required'
            })
            return
        
        await self.broadcast(
            connection.session_id,
            {
                'type': MessageType.ICE_CANDIDATE,
                'sender_id': connection.participant_id,
                'candidate': candidate,
                'timestamp': datetime.utcnow().isoformat()
            },
            exclude_connection=connection,
            target_participant=target_participant
        )
    
    async def _handle_recording_status(self, connection: ParticipantConnection, message: dict):
        """Handle recording status change."""
        status = message.get('status')
        
        if status not in ['started', 'stopped', 'paused', 'resumed']:
            await connection.send_message({
                'type': MessageType.ERROR,
                'detail': 'Invalid recording status'
            })
            return
        
        await self.broadcast(
            connection.session_id,
            {
                'type': MessageType.RECORDING_STATUS,
                'sender_id': connection.participant_id,
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
    
    async def _handle_heartbeat(self, connection: ParticipantConnection, message: dict):
        """Handle heartbeat message."""
        await connection.send_message({
            'type': MessageType.HEARTBEAT,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def get_session_participants(self, session_id: str) -> List[str]:
        """Get list of participant IDs in a session."""
        if session_id not in self.sessions:
            return []
        
        return [conn.participant_id for conn in self.sessions[session_id]]
    
    def get_session_stats(self, session_id: str) -> dict:
        """Get statistics for a session."""
        if session_id not in self.sessions:
            return {
                "participant_count": 0,
                "participants": []
            }
        
        connections = self.sessions[session_id]
        return {
            "participant_count": len(connections),
            "participants": [
                {
                    "participant_id": conn.participant_id,
                    "connected_at": conn.connected_at.isoformat(),
                    "connection_id": conn.connection_id
                }
                for conn in connections
            ]
        }

# Global WebSocket connection manager
websocket_manager = WebSocketConnectionManager()

async def websocket_endpoint(
    websocket: WebSocket, 
    session_id: str,
    participant_id: str = Query(..., description="Unique identifier for the participant"),
    db: AsyncSession = Depends(get_db)
):
    """
    Main WebSocket endpoint for session signaling.
    
    Args:
        websocket: Incoming WebSocket connection
        session_id: Unique identifier for the session
        participant_id: Unique identifier for the participant
        db: Database session dependency
    """
    connection = None
    
    try:
        # Connect the WebSocket
        connection = await websocket_manager.connect(websocket, session_id, participant_id, db)
        
        # Send initial connection confirmation
        await connection.send_message({
            'type': MessageType.PARTICIPANT_JOINED,
            'participant_id': participant_id,
            'session_participants': websocket_manager.get_session_participants(session_id),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Message handling loop
        while True:
            try:
                # Receive and parse WebSocket message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle the signaling message
                await websocket_manager.handle_signaling_message(connection, message, db)
            
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                await connection.send_message({
                    'type': MessageType.ERROR,
                    'detail': 'Invalid message format'
                })
            
            except Exception as e:
                logger.error(f"Error in message loop: {e}", exc_info=True)
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally: {participant_id}")
    
    except HTTPException as e:
        logger.warning(f"WebSocket connection rejected: {e.detail}")
        try:
            await websocket.close(code=e.status_code, reason=e.detail)
        except:
            pass
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    
    finally:
        # Clean up connection
        if connection:
            await websocket_manager.disconnect(connection)