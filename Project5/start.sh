#!/bin/bash

# Set environment variables
export FLASK_APP=quotes.py
export FLASK_ENV=development

# Start the Flask development server
python -m flask run
