# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the source code into the container at /app
COPY ./src /app/src

# Set the entrypoint to our new main.py file
# Uvicorn will run the FastAPI app.
# The host 0.0.0.0 is crucial for the container to be accessible from the outside.
# Render will automatically set the $PORT environment variable.
CMD ["uvicorn", "src.mysql_mcp_server.main:app", "--host", "0.0.0.0", "--port", "$PORT"]
