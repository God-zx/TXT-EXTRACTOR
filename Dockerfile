# Python Based Docker
FROM python:3.10-slim

# Installing System Packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    python3-dev \
    libffi-dev \
    git \
    curl \
    ffmpeg \
    aria2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Updating Pip
RUN pip install --upgrade pip

# Copying Requirements
COPY requirements.txt /requirements.txt

# Installing Requirements
RUN pip install --no-cache-dir -r /requirements.txt

# Creating Working Directory
RUN mkdir /EXTRACTOR
WORKDIR /EXTRACTOR

# Copying Project Files
COPY . /EXTRACTOR

# Make start.sh executable
RUN chmod +x start.sh

# Running Bot
CMD ["bash", "start.sh"]
