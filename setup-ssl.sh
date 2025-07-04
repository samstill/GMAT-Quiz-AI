#!/bin/bash

# SSL Certificate Setup Script for gmat.harshitpadha.me
# This script sets up Let's Encrypt SSL certificates for your domain

set -e

DOMAIN="gmat.harshitpadha.me"
EMAIL="harshitpadha@gmail.com"  # Replace with your email

echo "🔒 Setting up SSL certificates for $DOMAIN"
echo "=============================================="

# Create directories for SSL certificates
echo "📁 Creating SSL directories..."
mkdir -p ssl/certbot/conf
mkdir -p ssl/certbot/www

# Check if certificates already exist
if [ -d "ssl/certbot/conf/live/$DOMAIN" ]; then
    echo "✅ SSL certificates already exist for $DOMAIN"
    echo "🔄 To renew certificates, run: docker-compose exec certbot certbot renew"
    exit 0
fi

# Start containers without SSL first
echo "🚀 Starting containers for initial setup..."
docker-compose up -d

# Wait for nginx to be ready
echo "⏳ Waiting for nginx to be ready..."
sleep 10

# Request SSL certificate
echo "🔒 Requesting SSL certificate for $DOMAIN..."
docker-compose run --rm certbot certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

if [ $? -eq 0 ]; then
    echo "✅ SSL certificate obtained successfully!"
    echo "🔄 Restarting nginx with SSL configuration..."
    docker-compose restart frontend
    
    echo ""
    echo "🎉 SSL setup completed!"
    echo "========================"
    echo "🌐 Your site is now available at:"
    echo "   https://$DOMAIN"
    echo "   http://localhost (for local development)"
    echo ""
    echo "🔧 Certificate management:"
    echo "   • Auto-renewal is configured"
    echo "   • Certificates are stored in ./ssl/certbot/"
    echo "   • Manual renewal: docker-compose exec certbot certbot renew"
    
else
    echo "❌ Failed to obtain SSL certificate"
    echo "📋 Troubleshooting steps:"
    echo "   1. Ensure $DOMAIN points to this server's IP"
    echo "   2. Check DNS propagation: dig $DOMAIN"
    echo "   3. Verify port 80 is accessible from the internet"
    echo "   4. Check domain ownership"
    exit 1
fi
