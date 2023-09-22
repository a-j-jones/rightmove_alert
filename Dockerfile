# Use an official Python runtime as the base image
FROM python:3.11-slim

# Set environment variables to non-interactive (this prevents some prompts)
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /app

# Install system dependencies and Ruby
RUN apt-get update && \
    apt-get install -y ruby-full build-essential && \
    apt-get clean

# Install bootstrap-email gem
RUN gem install bootstrap-email

# First, copy only the requirements.txt to leverage Docker cache
COPY requirements.txt /app/

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the current directory contents into the container at /app
COPY . /app/

# Specify the command to run on container start
CMD ["python", "app.py"]
