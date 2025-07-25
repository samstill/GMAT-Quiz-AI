#!/bin/bash

# Generate SSL certificates for gmat.harshitpadha.me
# This script generates SSL certificates using certbot

echo "Generating SSL certificates for gmat.harshitpadha.me..."

# Create SSL directories
mkdir -p ssl/certbot/conf
mkdir -p ssl/certbot/www

# Generate certificates using certbot
docker run --rm \
  -v $(pwd)/ssl/certbot/conf:/etc/letsencrypt \
  -v $(pwd)/ssl/certbot/www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email harshitpadha@gmail.com \
  --agree-tos \
  --no-eff-email \
  -d gmat.harshitpadha.me

echo "SSL certificates generated!"
echo "Now you can use Cloudflare 'Full' SSL mode."
