# GMAT Quiz Application - Docker Setup

This repository contains a comprehensive GMAT Quiz application with Docker support for easy deployment.

## 🚀 Quick Start (One Command Setup)

### For Windows Users:
```bash
start-docker.bat
```

### For Linux/Mac Users:
```bash
chmod +x start-docker.sh
./start-docker.sh
```

That's it! The application will be available at `http://localhost`

## 📋 Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **Docker Compose** (usually included with Docker Desktop)

### Install Docker:
- **Windows/Mac**: [Docker Desktop](https://docs.docker.com/desktop/)
- **Linux**: [Docker Engine](https://docs.docker.com/engine/install/)

## 🛠️ Manual Setup (Alternative)

If you prefer to run commands manually:

1. **Clone and navigate to the project:**
   ```bash
   cd "GMAT Quiz"
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Build and start the application:**
   ```bash
   docker-compose up --build -d
   ```

4. **Access the application:**
   - Main Application: http://localhost
   - API Documentation: http://localhost:8000/docs

## 🔧 Configuration

### Environment Variables

Edit the `.env` file to customize your setup:

```env
# Google Gemini API Key (optional - can be provided from frontend)
GOOGLE_API_KEY=your_google_api_key_here

# User registration settings
ALLOW_USER_REGISTRATION=true
```

### Data Persistence

The following directories are automatically mounted to persist data:
- `./quiz.db` - Main database
- `./user_databases/` - Individual user databases
- `./JSON/` - Quiz questions and data
- `./images/` - Question images and assets

## 📋 Docker Commands

### Basic Operations:
```bash
# Start the application
docker-compose up -d

# Stop the application
docker-compose down

# View logs
docker-compose logs -f

# Restart the application
docker-compose restart

# Rebuild the application
docker-compose up --build -d
```

### Development:
```bash
# Build without starting
docker-compose build

# View running containers
docker-compose ps

# Execute commands in the container
docker-compose exec gmat-quiz-app bash
```

## 🔍 Troubleshooting

### Application won't start:
1. Check if ports are available:
   ```bash
   netstat -an | findstr :8000  # Windows
   lsof -i :8000                # Linux/Mac
   ```

2. View detailed logs:
   ```bash
   docker-compose logs gmat-quiz-app
   ```

### Reset everything:
```bash
# Stop and remove containers, networks
docker-compose down --remove-orphans

# Remove images (optional)
docker-compose down --rmi all

# Start fresh
docker-compose up --build -d
```

### Permission issues (Linux/Mac):
```bash
sudo chown -R $USER:$USER .
chmod +x start-docker.sh
```

## 🏗️ Architecture

The Docker setup includes:

- **FastAPI Backend** - Serves API endpoints and static files
- **SQLite Database** - Persistent data storage
- **Static File Serving** - HTML, CSS, JS, and images
- **Volume Mounts** - Data persistence across container restarts

## 📁 Project Structure

```
GMAT Quiz/
├── Dockerfile              # Container build instructions
├── docker-compose.yml      # Multi-service orchestration
├── start-docker.bat        # Windows one-command setup
├── start-docker.sh         # Linux/Mac one-command setup
├── .env.example            # Environment template
├── .dockerignore           # Docker build exclusions
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── index.html              # Frontend entry point
├── quiz.db                 # Main database
├── user_databases/         # Individual user data
├── JSON/                   # Quiz questions
└── images/                 # Question images
```

## 🔒 Security Notes

- The application runs on port 8000 by default
- Database files are persisted locally for data safety
- API keys are managed through environment variables
- User authentication is handled by the application

## 📞 Support

If you encounter any issues:

1. Check the application logs: `docker-compose logs -f`
2. Ensure Docker is running properly
3. Verify port 8000 is not in use by another application
4. Try rebuilding: `docker-compose up --build -d`

---

**🎯 Ready to start your GMAT prep journey? Run the setup script and dive in!**
