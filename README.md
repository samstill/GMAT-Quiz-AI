# GMAT Quiz Application

A comprehensive web-based GMAT (Graduate Management Admission Test) preparation platform built with FastAPI backend and modern web technologies. This application provides quiz management, performance tracking, AI-powered analysis, and flashcard functionality to help students prepare for the GMAT Focus Edition.

## 🚀 Features

### Core Functionality
- **Multi-Quiz Management**: Create, edit, and manage multiple GMAT quizzes
- **Question Types Support**: Quantitative, Verbal (RC/CR), and Data Insights sections
- **Reading Comprehension**: Full support for RC passages with linked questions
- **Performance Tracking**: Detailed analytics and progress monitoring
- **AI-Powered Analysis**: Gemini AI integration for personalized performance insights
- **Flashcard System**: Create and manage study flashcards with visual components
- **Image Support**: Upload and display images for questions
- **Time Management**: Built-in timer and time tracking for realistic test simulation
- **User Authentication**: Secure login and registration with API key management
- **Per-User Database**: Each user has their own isolated database for quiz data

### Advanced Features
- **Detailed Performance Review**: Question-by-question analysis with explanations
- **User Explanations**: Add personal notes and explanations for incorrect answers
- **Bulk Question Import**: JSON-based bulk question upload
- **Performance Summary**: Statistical analysis by difficulty, question type, and subsection
- **RESTful API**: Complete API for integration and data management
- **Rate-Limited AI**: Gemini API integration with proper rate limiting for free tier

## 🏗️ Architecture

- **Backend**: FastAPI (Python) with SQLAlchemy ORM
- **Database**: Multi-database SQLite architecture
  - Main authentication database (`quiz.db`)
  - Per-user isolated databases (`user_databases/{user_id}.db`)
- **Frontend**: Modern HTML/CSS/JavaScript with responsive design
- **AI Integration**: Google Gemini 2.0 Flash API
- **File Storage**: Local image storage with static file serving

## 📋 Prerequisites

- **Python 3.8+** (Python 3.11 recommended)
- **Google Gemini API Key** (free tier available)
- **Modern web browser** (Chrome, Firefox, Safari, Edge)
- **Windows OS** (for batch scripts) or cross-platform Python environment

## 🛠️ Installation & Setup

### Option 1: Automated Setup (Windows)

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd "GMAT Quiz"
   ```

2. **Run the automated setup**
   ```bash
   setup.bat
   ```
   
   This script will:
   - Check and install Python if needed
   - Create a virtual environment
   - Install all dependencies
   - Set up the database
   - Configure environment variables

3. **Configure your API key**
   - Open `.env` file
   - Replace the placeholder with your actual Gemini API key:
     ```
     GOOGLE_API_KEY=your_actual_api_key_here
     ```

4. **Start the application**
   ```bash
   start.bat
   ```

### Option 2: Manual Setup (Cross-Platform)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "GMAT Quiz"
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env and add your Gemini API key
   GOOGLE_API_KEY=your_actual_api_key_here
   ```

5. **Start the application**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

## 🔧 Configuration

### Multi-Database Architecture

The application uses a split-database architecture:

1. **Authentication Database** (`quiz.db`):
   - Stores user accounts and API keys only
   - Handles all authentication operations
   - Used by all users for login/registration

2. **User Databases** (`user_databases/{user_id}.db`):
   - Each user gets their own isolated database
   - Stores user-specific quizzes, questions, and performance data
   - Automatically created on user registration
   - Complete data isolation between users

To set up the multi-database structure:
```bash
# Run the user database setup script
setup_user_dbs.bat
```

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Required: Google Gemini API Key
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional: Database Configuration
DATABASE_URL=sqlite:///./quiz.db

# Optional: Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

### Getting a Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create a new API key
4. Copy the key to your `.env` file

**Note**: The free tier includes 15 requests per minute and 1,500 requests per day.

## 🚀 Usage

### Starting the Application

1. **Using batch files (Windows)**:
   ```bash
   start.bat
   ```

2. **Manual start**:
   ```bash
   # Activate virtual environment first
   uvicorn main:app --reload --port 8000
   ```

3. **Access the application**:
   - Main Interface: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Alternative API Docs: http://localhost:8000/redoc

### Core Workflows

#### 1. Creating Quizzes
- Navigate to "Manage Quizzes"
- Create a new quiz with name and time limit
- Add questions individually or bulk import from JSON

#### 2. Adding Questions
- Support for three question types: Quant, Verbal, Data Insights
- Upload images for visual questions
- Link Reading Comprehension questions to passages
- Set difficulty levels and explanations

#### 3. Taking Quizzes
- Select quiz from main interface
- Built-in timer with automatic submission
- Real-time progress tracking
- Immediate results with detailed breakdown

#### 4. Performance Analysis
- View detailed performance history
- AI-powered insights and recommendations
- Statistical analysis by type and difficulty
- Export and review incorrect answers

#### 5. Flashcard Management
- Create individual flashcards or sets
- Visual and text components
- Organize by topics
- Review and study mode

## 📁 Project Structure

```
GMAT Quiz/
├── main.py                # FastAPI application entry point
├── models.py              # SQLAlchemy database models
├── ai_tools.py            # Gemini AI integration and tools
├── migrate_db.py          # Database migration script for auth DB
├── migrate_user_db.py     # Script to create and populate user DBs
├── setup_user_dbs.bat     # User database setup script
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore rules
├── setup.bat              # Windows setup script
├── start.bat              # Windows start script
├── quiz.db                # Main authentication database (auto-created)
├── user_databases/        # Directory containing per-user databases
│   └── {user_id}.db       # Individual user database files
├── index.html             # Main application interface
├── quiz.html              # Quiz taking interface
├── manage_quizzes.html    # Quiz management interface
├── manage_questions.html  # Question management interface
├── performance.html       # Performance tracking interface
├── images/                # Uploaded question images
├── JSON/                  # Sample question data
│   ├── Quant/             # Quantitative questions
│   ├── Verbal/            # Verbal questions
│   └── Data Insights/     # Data Insights questions
├── Backup/                # Backup files
├── Temp/                  # Temporary development files
└── __pycache__/           # Python cache (auto-generated)
```

## 🔌 API Endpoints

### Quiz Management
- `GET /api/quizzes/` - List all quizzes
- `POST /api/quizzes/` - Create new quiz
- `GET /api/quizzes/{quiz_id}` - Get specific quiz
- `DELETE /api/quizzes/{quiz_id}` - Delete quiz

### Question Management
- `GET /api/quizzes/{quiz_id}/questions/` - Get quiz questions
- `POST /api/quizzes/{quiz_id}/questions/` - Add question to quiz
- `PUT /api/questions/{question_id}` - Update question
- `DELETE /api/questions/{question_id}` - Delete question
- `POST /api/quizzes/{quiz_id}/questions/bulk/` - Bulk add questions

### Performance Tracking
- `GET /api/performance/` - List performance records
- `POST /api/performance/` - Save quiz results
- `GET /api/performance/{performance_id}` - Get specific performance
- `DELETE /api/performance/{performance_id}` - Delete performance record
- `GET /api/performance/summary/{quiz_id}` - Get performance summary

### AI Analysis
- `POST /api/ai/analyze` - Get AI-powered performance analysis

### Flashcards
- `GET /api/flashcards/list` - List flashcard sets
- `POST /api/flashcards/save` - Save flashcard set
- `GET /api/flashcards/{flashcard_set_id}` - Get flashcard set
- `DELETE /api/flashcards/delete/{flashcard_set_id}` - Delete flashcard set

## 🧪 Testing

Run the included test files to verify functionality:

```bash
# Test flashcard functionality
python test_flashcards.py
python test_flashcards_list.py
python test_flashcards_delete.py
```

## 🔧 Development

### Adding New Features

1. **Database Changes**: Update `models.py` and create migrations
2. **API Endpoints**: Add new routes in `main.py`
3. **Frontend**: Modify HTML/CSS/JS files
4. **AI Tools**: Extend `ai_tools.py` for new AI functionality

### Code Style

- Follow PEP 8 for Python code
- Use type hints for function parameters and return values
- Add docstrings for all public functions and classes
- Maintain consistent error handling patterns

## 📊 Database Schema

The application uses SQLite with the following main tables:

- **quizzes**: Quiz metadata and settings
- **questions**: Individual quiz questions with options and answers
- **rc_passages**: Reading comprehension passages
- **performance**: Quiz attempt results and statistics
- **user_explanations**: Personal notes and explanations
- **flashcard_sets**: Flashcard collections
- **individual_flashcards**: Single flashcards

## 🔒 Security Considerations

- API keys are stored in environment variables
- Input validation on all API endpoints
- SQL injection protection via SQLAlchemy ORM
- Rate limiting on AI API calls
- File upload restrictions for images

## 🐛 Troubleshooting

### Common Issues

1. **"GOOGLE_API_KEY environment variable is required"**
   - Ensure `.env` file exists with valid API key
   - Check that `python-dotenv` is installed

2. **"Permission denied" on Windows**
   - Run terminal as Administrator
   - Check antivirus software isn't blocking files

3. **Database errors**
   - Delete `quiz.db` file to reset database
   - Restart application to trigger auto-migration

4. **AI API errors**
   - Verify API key is correct and active
   - Check rate limits (15 requests/minute for free tier)
   - Ensure internet connection is stable

### Getting Help

- Check the API documentation at `/docs` endpoint
- Review error logs in the terminal
- Verify all dependencies are correctly installed
- Ensure Python version compatibility (3.8+)

## 📄 License

This project is open source. Please refer to the license file for usage terms and conditions.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📞 Support

For technical support or feature requests, please create an issue in the project repository with:
- Detailed description of the problem
- Steps to reproduce
- System information (OS, Python version)
- Error messages or logs

---

**Made with ❤️ for GMAT test preparation**
