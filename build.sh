#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Create directories for file uploads (on persistent disk if available)
mkdir -p user_resumes
mkdir -p user_transcripts
mkdir -p uploads
mkdir -p generated_cover_letters

# If persistent disk is mounted, create symlinks
if [ -d "/opt/render/project/src/user_data" ]; then
    mkdir -p /opt/render/project/src/user_data/user_resumes
    mkdir -p /opt/render/project/src/user_data/user_transcripts

    # Replace local dirs with symlinks to persistent disk
    rm -rf user_resumes user_transcripts
    ln -sf /opt/render/project/src/user_data/user_resumes user_resumes
    ln -sf /opt/render/project/src/user_data/user_transcripts user_transcripts
fi
