# 🚀 One-Command Docker Setup for GMAT Quiz Application

## Quick Start - Just Run One Command!

### Windows Users:
```batch
start-docker.bat
```

### Linux/Mac Users:
```bash
chmod +x start-docker.sh && ./start-docker.sh
```

**That's it!** Your GMAT Quiz application will be running at `http://localhost` (port 80) in about 30 seconds.

---

## 📋 What the Setup Does

The one-command setup will:

1. ✅ Check if Docker is installed
2. ✅ Create environment configuration
3. ✅ Create necessary directories
4. ✅ Build the Docker container
5. ✅ Start the application
6. ✅ Verify everything is working
7. ✅ Display access information

## 🔧 Configuration

The application is pre-configured and ready to use. If you want to add your Google Gemini API key for AI features:

1. Edit the `.env` file that gets created
2. Set `GOOGLE_API_KEY=your_actual_api_key`
3. Restart with: `docker-compose restart`

## 📊 Features Available

- 🎯 **Complete GMAT Quiz Platform**
- 📚 **Multiple Quiz Types** (Quant, Verbal, Data Insights)
- 👥 **User Management** & Authentication
- 📈 **Performance Tracking** & Analytics
- 🤖 **AI-Powered Explanations** (with API key)
- 💾 **Persistent Data Storage**
- 🔄 **Auto-save Progress**

## 🛠️ Docker Management

### Essential Commands:
```bash
# View application status
docker-compose ps

# View logs
docker-compose logs -f

# Stop application
docker-compose down

# Restart application
docker-compose restart

# Update application
docker-compose up --build -d
```

### Data Management:
```bash
# Backup your data
cp quiz.db quiz-backup-$(date +%Y%m%d).db

# View database files
ls -la user_databases/
```

## 🔍 Troubleshooting

### Common Issues:

**Port already in use:**
```bash
# Find what's using port 80
netstat -an | findstr :80   # Windows
lsof -i :80                 # Linux/Mac

# Use different port
# Edit docker-compose.yml: "8080:80"
```

**Docker not found:**
- Install Docker Desktop from https://docs.docker.com/get-docker/

**Permission denied (Linux/Mac):**
```bash
sudo chown -R $USER:$USER .
chmod +x start-docker.sh
```

**Application won't start:**
```bash
# Check detailed logs
docker-compose logs frontend
docker-compose logs backend

# Restart everything
docker-compose down && docker-compose up -d
```

## 📁 File Structure

```
GMAT Quiz/
├── 🐳 start-docker.bat        # Windows setup script
├── 🐳 start-docker.sh         # Linux/Mac setup script
├── 🐳 Dockerfile              # Container definition
├── 🐳 docker-compose.yml      # Service orchestration
├── ⚙️ .env                    # Environment config (created automatically)
├── 🎯 main.py                 # FastAPI backend
├── 🌐 index.html              # Frontend entry
├── 💾 quiz.db                 # Main database
├── 👥 user_databases/         # User data
├── 📊 JSON/                   # Quiz questions
└── 🖼️ images/                 # Question images
```

## 🔒 Security & Data

- ✅ **Local Data**: All data stays on your machine
- ✅ **Isolated**: Runs in Docker container
- ✅ **Persistent**: Data survives container restarts
- ✅ **Backups**: Easy to backup database files

## 📞 Need Help?

1. **Check logs first**: `docker-compose logs -f`
2. **Restart if needed**: `docker-compose restart`
3. **Reset everything**: `docker-compose down && docker-compose up -d`

---

**🎓 Ready to ace your GMAT? Just run the setup script and start practicing!**
