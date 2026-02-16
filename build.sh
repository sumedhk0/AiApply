#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Create directories for file uploads
mkdir -p user_resumes
mkdir -p user_transcripts
mkdir -p uploads
mkdir -p generated_cover_letters
