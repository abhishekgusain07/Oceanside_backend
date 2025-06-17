"""
Custom exceptions for the application.
"""

class BaseApplicationError(Exception):
    """Base class for application-specific exceptions."""
    pass

class SessionCreationError(BaseApplicationError):
    """
    Raised when there is an error creating a session.
    
    Attributes:
        message (str): Detailed error message
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class SessionNotFoundError(BaseApplicationError):
    """
    Raised when a requested session cannot be found.
    
    Attributes:
        session_id (str): The ID of the session that was not found
        message (str): Detailed error message
    """
    def __init__(self, session_id: str, message: str = None):
        self.session_id = session_id
        self.message = message or f"Session {session_id} not found"
        super().__init__(self.message)

class SessionAccessError(BaseApplicationError):
    """
    Raised when there is an unauthorized attempt to access a session.
    
    Attributes:
        session_id (str): The ID of the session
        user_id (str): The ID of the user attempting access
        message (str): Detailed error message
    """
    def __init__(self, session_id: str, user_id: str, message: str = None):
        self.session_id = session_id
        self.user_id = user_id
        self.message = message or f"User {user_id} does not have access to session {session_id}"
        super().__init__(self.message)

class SessionParticipantError(BaseApplicationError):
    """
    Raised when there is an error related to session participants.
    
    Attributes:
        session_id (str): The ID of the session
        participant_id (str): The ID of the participant
        message (str): Detailed error message
    """
    def __init__(self, session_id: str, participant_id: str, message: str = None):
        self.session_id = session_id
        self.participant_id = participant_id
        self.message = message or f"Error with participant {participant_id} in session {session_id}"
        super().__init__(self.message)

class SessionCapacityError(BaseApplicationError):
    """
    Raised when a session has reached its maximum participant capacity.
    
    Attributes:
        session_id (str): The ID of the session
        max_participants (int): Maximum number of participants allowed
        message (str): Detailed error message
    """
    def __init__(self, session_id: str, max_participants: int, message: str = None):
        self.session_id = session_id
        self.max_participants = max_participants
        self.message = message or f"Session {session_id} has reached its maximum capacity of {max_participants} participants"
        super().__init__(self.message) 