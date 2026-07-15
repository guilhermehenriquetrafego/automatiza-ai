FROM python:3.12-slim

# Install dependencies needed for Chrome + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    && wget -q -O /tmp/google-chrome-stable.deb \
       "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" \
    && (apt-get install -y /tmp/google-chrome-stable.deb || apt-get -f install -y) \
    && rm /tmp/google-chrome-stable.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
