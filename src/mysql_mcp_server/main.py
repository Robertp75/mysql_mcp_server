import os
import json
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
import mysql.connector

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO)
load_dotenv()

# --- Configuration & Security ---
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable is not set.")

DB_HOST = os.getenv("MYSQL_HOST")
DB_PORT = os.getenv("MYSQL_PORT", 3306)
DB_USER = os.getenv("MYSQL_USER")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME = os.getenv("MYSQL_DATABASE")

if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
    raise ValueError("One or more MySQL environment variables are missing.")

auth_scheme = HTTPBearer()

def verify_api_key(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    """Dependency to verify the API key."""
    if not creds or creds.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return creds.credentials

def get_db_connection():
    """Establishes and returns a new database connection."""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return connection
    except mysql.connector.Error as err:
        logging.error(f"Database connection failed: {err}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {err}")

# --- Pydantic Models ---
class McpRequest(BaseModel):
    mcp_request: dict

# --- FastAPI Application ---
app = FastAPI(
    title="MySQL MCP Web Server",
    description="A secure web API to interact with a MySQL database.",
    version="1.1.0"
)

# --- Core Logic ---
def handle_request(request_data: dict):
    verb = request_data.get("verb")
    
    if verb == "list_resources":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = [item[0] for item in cursor.fetchall()]
        cursor.close()
        conn.close()
        response_data = {"resources": [{"name": table, "description": f"Table: {table}"} for table in tables]}
    
    elif verb == "read":
        table_name = request_data.get("parameters", {}).get("name")
        if not table_name:
            return {"error": "Table name is required for read verb."}
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 100;") # Added LIMIT for safety
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        response_data = {"data": rows}

    elif verb == "execute":
        statement = request_data.get("parameters", {}).get("statement")
        if not statement:
            return {"error": "SQL statement is required for execute verb."}
        
        # Basic security check
        if "delete" in statement.lower() or "drop" in statement.lower() or "update" in statement.lower() or "insert" in statement.lower():
             return {"error": "Only SELECT statements are allowed for security reasons."}

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(statement)
            results = cursor.fetchall()
            response_data = {"results": results}
        except mysql.connector.Error as err:
            response_data = {"error": f"SQL Error: {err}"}
        finally:
            cursor.close()
            conn.close()

    else:
        response_data = {"error": f"Unsupported verb: {verb}"}
        
    return response_data

# --- API Endpoints ---
@app.post("/query", dependencies=[Depends(verify_api_key)])
async def process_query(request: McpRequest):
    """Receives an MCP-formatted request, processes it, and returns the result."""
    try:
        response = handle_request(request.mcp_request)
        if "error" in response:
            # Handle business logic errors gracefully
            return HTTPException(status_code=400, detail=response["error"])
        return response
    except HTTPException as http_exc:
        # Re-raise exceptions from dependencies (like auth or db connection)
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors
        logging.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/health")
def health_check():
    """A simple health check endpoint."""
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "ok", "database_connection": "successful"}
    except Exception as e:
        return {"status": "error", "database_connection": "failed", "detail": str(e)}

# --- Run Server (for local testing) ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
