from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import pytz
import json
from typing import List

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
df_in=0
# Create initial DataFrame if it doesn't exist
try:
    df_in = pd.read_csv('chat_messages.csv')
except FileNotFoundError:
    df_in = pd.DataFrame(columns=['id', 'name', 'text', 'timestamp'])
    df_in.to_csv('chat_messages.csv', index=False)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        df_in = pd.read_csv('chat_messages.csv')
        # Send existing messages on connection
        messages = df_in.to_dict('records')
        await websocket.send_json({"type": "history", "messages": messages})
        
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "message":
                # Add message to DataFrame
                df_in = pd.read_csv('chat_messages.csv')
                new_message = pd.DataFrame([{
                    'id': len(df_in) + 1,
                    'name': data['name'],
                    'text': data['text'],
                    'timestamp': datetime.now(pytz.UTC).isoformat()
                }])
                
                df_in = pd.concat([df_in, new_message], ignore_index=True)
                df_in = df_in.tail(100)  # Keep only last 100 messages
                df_in.to_csv('chat_messages.csv', index=False)
                
                # Broadcast to all clients
                await manager.broadcast({
                    "type": "message",
                    "message": new_message.to_dict('records')[0]
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
