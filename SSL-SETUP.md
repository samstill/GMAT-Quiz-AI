# 🔒 SSL Certificate Setup Guide for gmat.harshitpadha.me

This guide will help you set up SSL certificates for your GMAT Quiz application using Let's Encrypt.

## 📋 Prerequisites

1. **Domain Setup**: Ensure `gmat.harshitpadha.me` points to your server's public IP
2. **DNS Propagation**: Verify DNS has propagated (use `dig gmat.harshitpadha.me` or online tools)
3. **Port Access**: Ensure ports 80 and 443 are accessible from the internet
4. **Docker Running**: Have Docker and Docker Compose installed

## 🚀 Quick SSL Setup

### Option 1: Automated Setup (Recommended)

**Windows:**
```batch
setup-ssl.bat
```

**Linux/Mac:**
```bash
chmod +x setup-ssl.sh
./setup-ssl.sh
```

### Option 2: Manual Setup

1. **Start the application:**
   ```bash
   docker-compose up -d
   ```

2. **Request SSL certificate:**
   ```bash
   docker-compose run --rm certbot certbot certonly \
     --webroot \
     --webroot-path=/var/www/certbot \
     --email harshitpadha@gmail.com \
     --agree-tos \
     --no-eff-email \
     -d gmat.harshitpadha.me
   ```

3. **Restart nginx:**
   ```bash
   docker-compose restart frontend
   ```

## 🔧 Configuration Details

### Nginx SSL Configuration

The nginx configuration includes:

- **HTTP to HTTPS Redirect**: All HTTP traffic redirected to HTTPS
- **SSL Security**: Modern TLS 1.2/1.3 protocols and secure ciphers
- **Security Headers**: HSTS, XSS protection, content type options
- **ACME Challenge**: Support for Let's Encrypt certificate validation

### Certificate Management

- **Auto-Renewal**: Certificates renew automatically every 12 hours
- **Storage**: Certificates stored in `./ssl/certbot/conf/`
- **Backup**: Certificate files are backed up with your project

## 🌐 Access URLs

After SSL setup:

- **Production**: https://gmat.harshitpadha.me
- **Development**: http://localhost
- **API**: https://gmat.harshitpadha.me/api/ or http://localhost:8000
- **Docs**: https://gmat.harshitpadha.me/docs or http://localhost:8000/docs

## 🔍 Troubleshooting

### Common Issues

**Certificate request fails:**
```bash
# Check DNS
dig gmat.harshitpadha.me

# Test HTTP access
curl -I http://gmat.harshitpadha.me

# Check logs
docker-compose logs frontend
docker-compose logs certbot
```

**Port 80/443 not accessible:**
```bash
# Check if ports are open
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443

# Test from external server
curl -I http://your-server-ip
```

**Domain not pointing to server:**
- Update DNS A record to point to your server's public IP
- Wait for DNS propagation (can take up to 48 hours)
- Use online DNS propagation checkers

### Manual Certificate Renewal

```bash
# Renew certificates manually
docker-compose exec certbot certbot renew

# Restart nginx after renewal
docker-compose restart frontend
```

### SSL Certificate Information

```bash
# Check certificate details
docker-compose exec certbot certbot certificates

# Test SSL configuration
openssl s_client -connect gmat.harshitpadha.me:443 -servername gmat.harshitpadha.me
```

## 🔒 Security Features

### SSL Configuration
- **TLS 1.2/1.3**: Modern protocols only
- **Strong Ciphers**: ECDHE and DHE key exchange
- **HSTS**: HTTP Strict Transport Security enabled
- **Security Headers**: Protection against common attacks

### Certificate Details
- **Provider**: Let's Encrypt (free, trusted CA)
- **Validity**: 90 days (auto-renews every 60 days)
- **Type**: Domain validated (DV)
- **Encryption**: RSA 2048-bit or ECDSA

## 📁 File Structure

```
ssl/
├── certbot/
│   ├── conf/           # Certificate files
│   │   └── live/
│   │       └── gmat.harshitpadha.me/
│   │           ├── fullchain.pem
│   │           ├── privkey.pem
│   │           └── cert.pem
│   └── www/            # ACME challenge files
```

## 🔄 Maintenance

### Regular Tasks
- **Monitor Expiry**: Certificates auto-renew, but monitor logs
- **Update nginx**: Keep nginx image updated for security
- **Backup Certificates**: Include `ssl/` directory in backups

### Updating Domain/Email
1. Edit `setup-ssl.sh` or `setup-ssl.bat`
2. Update `DOMAIN` and `EMAIL` variables
3. Re-run the setup script

## 🆘 Support

If you encounter issues:

1. **Check logs**: `docker-compose logs frontend certbot`
2. **Verify DNS**: Ensure domain points to your server
3. **Test connectivity**: Ensure ports 80/443 are accessible
4. **Certificate status**: `docker-compose exec certbot certbot certificates`

---

**🔐 Your GMAT Quiz application is now secured with SSL encryption!**
