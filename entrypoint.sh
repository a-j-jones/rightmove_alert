#!/bin/bash

# Initialize the database if it doesn't exist
if [ ! -f /data/database.db ]; then
  cp /app/database/database.db /data/
fi

# Run the main application
exec "$@"
