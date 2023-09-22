# Use an official Python runtime as the base image
FROM python:3.11-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /app

# Install system dependencies and Ruby
RUN apt-get update && \
    apt-get install -y ruby-full build-essential && \
    apt-get clean

# Install bootstrap-email gem
RUN gem install bootstrap-email

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . /app/

# Use the entrypoint script to initialize the database
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "app.py"]
