Of course. Here is a new architectural blueprint for your FastAPI backend, refactored to use `python-socketio` for signaling and a background worker for processing. It's designed to be simpler, more robust, and mirrors the effective patterns from the reference application you liked, while keeping the best parts of your original design.

---

## **Architectural Blueprint: Refactored with Socket.IO & Celery**

This document outlines the revised system architecture for the multi-track recording platform. This design simplifies the backend by replacing the manual WebSocket implementation with `python-socketio` and offloading heavy video processing to a dedicated background worker using Celery.

### **High-Level Diagram**

```
                     +---------------------------+
                     |   Cloud Storage (S3/GCS)  |
                     | (High-Quality Recordings) |
                     +-------------+-------------+
                                   ^
          (4. Direct Upload)       |       (4. Direct Upload)
+----------------------------------+----------------------------------+
|                                  |                                  |
|  +------------------------+      |       +------------------------+  |
|  |   Participant A        |      |       |   Participant B        |  |
|  |  (Next.js Frontend)    |      |       |  (Next.js Frontend)    |  |
|  +------------------------+      |       +------------------------+  |
|      |         ^                 |                  |        ^      |
|      | (2.      | (3. Local       |                  | (2.     | (3. Local
|      | WebRTC   | Recording)     |                  | WebRTC  | Recording)
|      | Live     |                |                  | Live    |
|      | Stream)  |                |                  | Stream) |
|      v         |                 |                  v        |      |
+------+---------+-----------------|------------------+--------+------+
       < - - - - - - - - - - - >   |   < - - - - - - - - - - - - >
        (Peer-to-Peer Connection)  |    (Peer-to-Peer Connection)
                                   |
+----------------------------------+----------------------------------+
| (1. Socket.IO Events)            | (5. Celery Task)                 |
|                                  v                                  |
|                 +----------------+-----------------+    +-----------+------------+
|                 |       FastAPI Backend            |--->|  Redis / RabbitMQ      |
|                 | (Socket.IO Signaling & API)      |<---| (Job Queue)            |
|                 +----------------------------------+    +-----------+------------+
|                                                                     |
|                                                                     v
|                                                     +---------------+--------------+
|                                                     |   Celery Worker Process      |
|                                                     | (FFmpeg Video Processing)    |
|                                                     +------------------------------+
```

### **1. Core Components & Responsibilities**

**a. Next.js Frontend (The "Recording Studio")**
*   **Role:** User-facing application.
*   **Key Change:** Replaces native WebSocket logic with the `socket.io-client` library to communicate with the backend.
*   **Responsibilities:**
    *   **UI/UX:** Renders the video call interface.
    *   **API Communication:** Makes HTTP requests to FastAPI for creating sessions and getting upload URLs.
    *   **Socket.IO Client:** Emits and listens for structured events (`join_room`, `offer`, `answer`, etc.) for real-time signaling.
    *   **Local Recorder & Uploader:** Unchanged. Continues to record high-quality local streams and upload chunks directly to cloud storage using pre-signed URLs.

**b. FastAPI Backend (The "Control Tower")**
*   **Role:** Orchestrates sessions, signaling, and background jobs. It no longer manages raw WebSocket connections.
*   **Key Change:** Integrates the `python-socketio` library to handle real-time communication.
*   **Responsibilities:**
    *   **User & Recording API:** Provides RESTful endpoints for user auth, creating recordings, and generating guest tokens.
    *   **Socket.IO Server:** Manages rooms and broadcasts signaling events (`offer`, `answer`, `ice_candidate`) to the correct participants.
    *   **Upload Orchestration:** Provides the `/api/recordings/upload-url` endpoint to generate pre-signed URLs for direct-to-cloud uploads.
    *   **Job Dispatcher:** When a recording stops, it dispatches a video processing task to the Celery queue. It **does not** perform any video merging itself.

**c. Cloud Storage (The "Vault")**
*   **Role:** Unchanged. The permanent destination for raw recording chunks and final processed videos.

**d. Celery Worker & Queue (The "Processing Plant")**
*   **Role:** A new, separate background process dedicated to heavy, long-running tasks.
*   **Key Change:** Isolates video processing from the web-facing API, preventing server timeouts and improving responsiveness.
*   **Responsibilities:**
    *   **Task Consumption:** Listens to the job queue (Redis) for new video processing tasks.
    *   **Video Processing:** When a job is received, it downloads the relevant chunks from cloud storage, uses FFmpeg to concatenate and merge them, and uploads the final video back to storage.
    *   **Database Updates:** Updates the `recording` table with the final `video_url` upon successful completion.

### **2. The Architectural Flow: A Step-by-Step Session**

This is the new sequence of events, leveraging the updated components.

**Step 1: Host Creates a Recording Session**
1.  The Host clicks "Create Session" in the Next.js app.
2.  The frontend sends an authorized `POST` request to the FastAPI backend: `POST /api/recordings`.
3.  The backend:
    *   Creates a new entry in the `recording` table.
    *   Generates a unique `roomId`.
    *   Returns the `roomId` to the frontend.
4.  The frontend navigates to the studio page (`/session/{roomId}`) and establishes a Socket.IO connection.

**Step 2: Guest Joins the Session**
1.  The Host generates an invite link by hitting a new endpoint: `POST /api/recordings/{roomId}/guest-token`. This creates a short-lived `guest_token` in the database.
2.  The Guest clicks the link containing the `roomId` and `guestToken`.
3.  The Next.js app loads, validates the token (optional, can be done on the `join_room` event), and establishes its own Socket.IO connection.

**Step 3: The Socket.IO "Handshake" (Establishing the Live Call)**
*This process is now simpler and more declarative.*
1.  Upon connecting, both Host and Guest emit a `join_room` event to the server: `sio.emit('join_room', { 'roomId': '...', 'userType': 'host' })`.
2.  On the backend, the `join_room` handler receives this and uses `sio.enter_room(sid, roomId)` to place the client into a logical room.
3.  The WebRTC signaling flow begins, managed by Socket.IO's broadcasting:
    *   A new client (e.g., the Guest) emits an `offer`.
    *   The FastAPI server receives the `offer` and broadcasts it to all *other* clients in the same room: `await sio.emit('offer', data, room=roomId, skip_sid=sid)`.
    *   The Host's client receives the `offer` and emits an `answer`.
    *   The server broadcasts the `answer` back to the original sender.
    *   `ice_candidate` events are exchanged in the same manner.
4.  A direct peer-to-peer WebRTC connection is established.

**Step 4: Recording & Uploading (Dual-Track Magic)**
*This flow remains largely the same, which is a good thing.*
1.  The Host clicks "Record". The frontend emits a `start_recording_request` to the server.
2.  The server broadcasts a `start_recording` event to **all** clients in the room with a synchronized start time to ensure alignment.
3.  Each client's `MediaRecorder` starts, and the "Chunk & Upload Loop" begins, requesting pre-signed URLs from `GET /api/recordings/upload-url` and `PUT`-ing chunks directly to cloud storage.

**Step 5: Ending the Session & Offloading Processing**
1.  The Host clicks "Stop Recording".
2.  The frontend emits a `recording_stopped` event to the server, including the `roomId` and `userId`.
3.  The FastAPI backend receives this event. **Crucially, its only action is to enqueue a background job:** `process_video_task.delay(roomId=roomId, userId=userId)`. It immediately acknowledges the event.
4.  Simultaneously, the server broadcasts a `stop_rec` event to all clients in the room so their UIs can stop the recording state.
5.  A separate **Celery worker process**, running on potentially different infrastructure, picks up the `process_video_task` from the queue. It runs the FFmpeg logic, merges the video, uploads the final file, and updates the database. The user can see the final video in their dashboard once this is done.

### **3. API & Socket.IO Event Reference**

#### **REST API Endpoints (FastAPI)**

| Method | Endpoint                             | Description                                                              |
| :----- | :----------------------------------- | :----------------------------------------------------------------------- |
| `POST` | `/api/recordings`                    | Creates a new recording session. Returns a `roomId`.                     |
| `GET`  | `/api/recordings`                    | Lists all completed recordings for the authenticated user.               |
| `POST` | `/api/recordings/{roomId}/guest-token` | Generates a temporary, single-use invite token for a guest.              |
| `GET`  | `/api/recordings/upload-url`         | Generates a pre-signed URL for a client to upload one recording chunk.   |

#### **Socket.IO Events (Server-Side Handlers)**

| Event Name                | Triggered By | Action                                                                                                         |
| :------------------------ | :----------- | :------------------------------------------------------------------------------------------------------------- |
| `connect`                 | Client       | A new client connects to the server.                                                                           |
| `disconnect`              | Client       | A client disconnects. Server should handle cleanup if necessary.                                               |
| `join_room`               | Client       | Client requests to join a room. Server uses `sio.enter_room()`.                                                |
| `offer`, `answer`, `ice_candidate` | Client       | Client sends WebRTC signaling data. Server broadcasts it to the other participants in the room.          |
| `start_recording_request` | Host Client  | Host wants to start recording. Server broadcasts a synchronized `start_recording` event to all in the room. |
| `recording_stopped`       | Host Client  | Host stops recording. Server dispatches a background job to Celery for video processing.                       |