FROM python:3.12-slim

# Set working directory in the container
WORKDIR /app

# Install system dependencies required for some Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container
COPY . .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=index.py
ENV FLASK_ENV=development

# Run app.py when the container launches
CMD ["flask", "run", "--host=0.0.0.0"]