# main.py - Your FastAPI Backend with Multiple Quizzes, Detailed Performance Tracking, and Time Limit

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Path, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, Session # Import joinedload for eager loading
from sqlalchemy.exc import IntegrityError, OperationalError
import json
import os
import shutil
import datetime # To record submission time
import httpx # Required for making server-to-server API calls
import asyncio
import time
import hashlib
import secrets
from dotenv import load_dotenv
from google.api_core import retry, exceptions
from ai_tools import AVAILABLE_TOOLS, GEMINI_TOOLS, GEMINI_TOOL_CONFIG
from models import Base, QuizDB, RCPassageDB, QuestionDB, PerformanceDB, UserExplanationDB, FlashcardSetDB, IndividualFlashcardDB, UserDB, APIKeyDB

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
ALLOW_USER_REGISTRATION = os.environ.get("ALLOW_USER_REGISTRATION", "true").lower() == "true"

# --- Google AI Configuration with Rate Limiting ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
# Make GOOGLE_API_KEY optional - will be provided from frontend when needed
GEMINI_API_URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

if GOOGLE_API_KEY:
    print("Using Gemini API key from environment variables")
else:
    print("No Gemini API key found in environment. API key will be required from frontend for AI features.")

# Rate limiting configuration for Gemini free tier
# Free tier limits: 15 RPM (requests per minute), 1 million TPM (tokens per minute), 1,500 RPD (requests per day)
class RateLimiter:
    def __init__(self, requests_per_minute: int = 15, requests_per_day: int = 1500):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self.minute_requests = []
        self.daily_requests = []
        
    async def acquire(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()
        
        # Clean old requests (older than 1 minute and 1 day)
        self.minute_requests = [req_time for req_time in self.minute_requests if now - req_time < 60]
        self.daily_requests = [req_time for req_time in self.daily_requests if now - req_time < 86400]
        
        # Check if we need to wait for minute limit
        if len(self.minute_requests) >= self.requests_per_minute:
            sleep_time = 60 - (now - self.minute_requests[0])
            if sleep_time > 0:
                print(f"Rate limit: waiting {sleep_time:.1f}s for minute quota")
                await asyncio.sleep(sleep_time)
                return await self.acquire()  # Re-check after waiting
        
        # Check daily limit
        if len(self.daily_requests) >= self.requests_per_day:
            raise HTTPException(status_code=429, detail="Daily Gemini API quota exceeded. Please try again tomorrow.")
        
        # Record this request
        self.minute_requests.append(now)
        self.daily_requests.append(now)

# Global rate limiter instance
gemini_rate_limiter = RateLimiter()

# --- Database Configuration ---
# Main database for user authentication
MAIN_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/quiz.db")
main_engine = create_engine(
    MAIN_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
MainSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=main_engine)

# --- Database Models (SQLAlchemy ORM) ---
# Ensure data directory exists
os.makedirs('data', exist_ok=True)
os.makedirs('user_databases', exist_ok=True)

# Create auth tables in the main database
Base.metadata.create_all(bind=main_engine)

# --- Database dependency injection ---
def get_main_db():
    """Get a database session for the main authentication database"""
    db = MainSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_db(request: Request, db: Session = Depends(get_main_db)):
    """
    Get a database session for the current user's database.
    If no authenticated user, returns the main database for auth operations.
    """
    # Get the API key from the header
    api_key = request.headers.get("X-API-Key")
    
    # If no API key is provided, return the main database (for auth operations)
    if not api_key:
        yield db
        return
    
    # Query for active API key to get user ID
    db_api_key = db.query(APIKeyDB).filter(
        APIKeyDB.api_key == api_key,
        APIKeyDB.is_active == True
    ).first()
    
    # If API key not found or user not found, use main database
    if not db_api_key:
        yield db
        return
    
    # Check if API key has expired
    if db_api_key.expires_at and db_api_key.expires_at < datetime.datetime.utcnow():
        yield db
        return
    
    # Update last used timestamp
    db_api_key.last_used_at = datetime.datetime.utcnow()
    db.commit()
    
    # Get the user
    user = db.query(UserDB).filter(
        UserDB.id == db_api_key.user_id,
        UserDB.is_active == True
    ).first()
    
    if not user:
        yield db
        return
    
    # Create or get the user's database session
    user_db_session = UserDB.get_user_db_session(user.id)
    
    try:
        yield user_db_session
    finally:
        user_db_session.close()

# Default database dependency - works for both auth and user operations
get_db = get_user_db

def migrate_database():
    db = MainSessionLocal()
    try:
        db.execute(text("SELECT answer_explanation FROM questions LIMIT 1"))
        print("Database migration: answer_explanation column already exists")
    except OperationalError as e:
        if "no such column" in str(e).lower():
            try:
                db.execute(text("ALTER TABLE questions ADD COLUMN answer_explanation TEXT"))
                db.commit()
                print("Database migration: Successfully added answer_explanation column")
            except Exception as add_error:
                print(f"Database migration failed: {add_error}")
                db.rollback()
        else:
            print(f"Database migration check failed with unexpected error: {e}")
    except Exception as general_error:
        print(f"Database migration check failed: {general_error}")
    finally:
        db.close()

migrate_database()


# --- Pydantic Models (for Request/Response Validation) ---

# --- Authentication Models ---
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

class APIKeyCreate(BaseModel):
    key_name: str
    expires_in_days: Optional[int] = None  # Optional expiration in days

class APIKeyResponse(BaseModel):
    id: int
    key_name: str
    api_key: str
    is_active: bool
    created_at: datetime.datetime
    expires_at: Optional[datetime.datetime] = None
    
    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

# --- Quiz Models ---
class QuizBase(BaseModel):
    name: str
    time_limit_minutes: int

class QuizCreate(QuizBase):
    pass

class QuizResponse(QuizBase):
    id: int
    class Config:
        from_attributes = True

class RCPassageBase(BaseModel):
    title: Optional[str] = None
    passage_text: str

class RCPassageCreate(RCPassageBase):
    pass

class RCPassageResponse(RCPassageBase):
    id: int
    class Config:
        from_attributes = True


class QuestionBase(BaseModel):
    questionText: str
    options: List[str]
    correctAnswer: str
    answerExplanation: Optional[str] = None
    image: Optional[str] = None
    difficulty: str
    rc_id: Optional[int] = None
    question_type: str
    subsection: Optional[str] = None

class QuestionCreate(QuestionBase):
    pass

class QuestionResponse(BaseModel):
    id: int
    quiz_id: int
    rc_id: Optional[int] = None
    rc_passage: Optional[RCPassageResponse] = None
    questionText: str
    options: List[str]
    correctAnswer: str
    answerExplanation: Optional[str] = None
    image: Optional[str] = None
    difficulty: str
    question_type: str
    subsection: Optional[str] = None
    class Config:
        from_attributes = True

class DetailedQuestionResult(BaseModel):
    questionId: int
    correct: bool
    difficulty: str
    userAnswer: Optional[str] = None
    correctAnswer: str
    questionText: str
    options: List[str]
    question_type: str
    subsection: Optional[str] = None
    timeSpent: Optional[int] = None
    answerExplanation: Optional[str] = None

class DetailedPerformanceReview(BaseModel):
    questionId: int
    correct: bool
    userAnswer: Optional[str] = None
    correctAnswer: str
    questionText: str
    options: List[str]
    difficulty: str
    question_type: str
    subsection: Optional[str] = None
    timeSpent: Optional[int] = None
    answerExplanation: Optional[str] = None
    rc_passage: Optional[RCPassageResponse] = None
    userExplanation: Optional[str] = None

class UserExplanationBase(BaseModel):
    explanation_text: str

class UserExplanationCreate(UserExplanationBase):
    question_id: int
    class Config:
        populate_by_name = True

class UserExplanationUpdate(UserExplanationBase):
    pass

class UserExplanationResponse(UserExplanationBase):
    id: int
    performance_id: int
    question_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    class Config:
        from_attributes = True

class PerformanceCreate(BaseModel):
    quizId: int
    totalQuestions: int
    correctAnswers: int
    timeTakenSeconds: int
    detailedResults: List[DetailedQuestionResult]

class PerformanceResponse(BaseModel):
    id: int
    quizId: int
    timestamp: datetime.datetime
    totalQuestions: int
    correctAnswers: int
    timeTakenSeconds: int
    detailedResults: List[DetailedQuestionResult]
    class Config:
        from_attributes = True

class BulkQuestionCreate(BaseModel):
    questionText: str
    options: List[str]
    correctAnswer: str
    answerExplanation: Optional[str] = None
    difficulty: str
    rc_id: Optional[int] = None
    question_type: str
    subsection: Optional[str] = None


# --- Flashcard Models ---
class FlashcardFront(BaseModel):
    visual: str = ""
    text: str

class Flashcard(BaseModel):
    front: FlashcardFront
    back: str

class FlashcardSetCreate(BaseModel):
    name: str
    topics: Optional[str] = None
    flashcards: List[Flashcard]
    created_at: Optional[str] = None

class FlashcardSetResponse(BaseModel):
    id: int
    name: str
    topics: Optional[str] = None
    flashcards: List[Flashcard]
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

class IndividualFlashcardCreate(BaseModel):
    name: str
    topics: Optional[str] = None
    flashcard: Flashcard
    created_at: Optional[str] = None

class IndividualFlashcardResponse(BaseModel):
    id: int
    name: str
    topics: Optional[str] = None
    flashcard: Flashcard
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

# --- FastAPI Application Setup ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Mount static files for frontend (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="."), name="static")

# Add a route to serve the main page
@app.get("/")
async def serve_index():
    from fastapi.responses import FileResponse
    return FileResponse("index.html")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}

# --- Authentication Utilities ---
async def get_optional_user(
    api_key: str = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_main_db)
) -> Optional[UserDB]:
    """Dependency to get current user from API key if provided, otherwise None"""
    if not api_key:
        return None
    
    # Query for active API key
    db_api_key = db.query(APIKeyDB).filter(
        APIKeyDB.api_key == api_key,
        APIKeyDB.is_active == True
    ).first()
    
    if not db_api_key:
        return None
    
    # Check if API key has expired
    if db_api_key.expires_at and db_api_key.expires_at < datetime.datetime.utcnow():
        return None
    
    # Update last used timestamp
    db_api_key.last_used_at = datetime.datetime.utcnow()
    db.commit()
    
    # Get the user
    user = db.query(UserDB).filter(
        UserDB.id == db_api_key.user_id,
        UserDB.is_active == True
    ).first()
    
    return user

# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Quiz API!"}

# --- Authentication Endpoints ---

@app.post("/api/auth/register", response_model=UserResponse, status_code=201)
async def register_user(user_data: UserCreate, db: Session = Depends(get_main_db)):
    if not ALLOW_USER_REGISTRATION:
        raise HTTPException(status_code=403, detail="User registration is disabled")
    
    # Check if user already exists
    db_user = db.query(UserDB).filter(
        (UserDB.username == user_data.username) | (UserDB.email == user_data.email)
    ).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username or email already registered"
        )
    
    # Create new user
    db_user = UserDB(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password
    )
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
        
        # Create user's personal database
        user_db_path = UserDB.create_user_db(db_user.id)
        
        # Update user with the database path
        db_user.database_path = user_db_path
        db.commit()
        
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="User could not be created.")

@app.post("/api/auth/login")
async def login_for_api_key(form_data: LoginRequest, db: Session = Depends(get_main_db)):
    """
    Authenticate user and return an API key for accessing the application.
    """
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()
    if not user or user.password != form_data.password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure user has a database
    if not user.database_path or not os.path.exists(user.database_path):
        # Create user database if it doesn't exist
        user_db_path = UserDB.create_user_db(user.id)
        user.database_path = user_db_path
        db.commit()

    # Create or retrieve API key
    api_key = db.query(APIKeyDB).filter(APIKeyDB.user_id == user.id).first()
    if api_key:
        # Update last used timestamp
        api_key.last_used_at = datetime.datetime.utcnow()
        db.commit()
    else:
        # Create a new API key
        new_api_key = APIKeyDB.generate_api_key()
        db_api_key = APIKeyDB(
            user_id=user.id,
            key_name="default",
            api_key=new_api_key
        )
        db.add(db_api_key)
        db.commit()

    return {
        "message": "Login successful",
        "api_key": api_key.api_key if api_key else new_api_key,
        "username": user.username,
        "user_id": user.id
    }

@app.post("/api/auth/api-keys", response_model=APIKeyResponse, status_code=201)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: UserDB = Depends(get_optional_user),
    db: Session = Depends(get_main_db)
):
    """Generate a new API key for the authenticated user."""
    new_api_key_str = APIKeyDB.generate_api_key()
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=key_data.expires_in_days)
    
    db_api_key = APIKeyDB(
        user_id=current_user.id,
        key_name=key_data.key_name,
        api_key=new_api_key_str,
        expires_at=expires_at
    )
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    
    return db_api_key

@app.get("/api/auth/api-keys", response_model=List[APIKeyResponse])
async def get_user_api_keys(
    current_user: Optional[UserDB] = Depends(get_optional_user),
    db: Session = Depends(get_main_db)
):
    """List all active API keys for the authenticated user."""
    api_keys = db.query(APIKeyDB).filter(APIKeyDB.user_id == current_user.id).all()
    return api_keys

@app.delete("/api/auth/api-keys/{api_key_id}", status_code=204)
async def delete_api_key(
    api_key_id: int,
    current_user: Optional[UserDB] = Depends(get_optional_user),
    db: Session = Depends(get_main_db)
):
    """Delete an API key for the authenticated user."""
    db_api_key = db.query(APIKeyDB).filter(
        APIKeyDB.id == api_key_id,
        APIKeyDB.user_id == current_user.id
    ).first()
    
    if db_api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")
        
    db.delete(db_api_key)
    db.commit()
    return


# --- Quiz Management Endpoints ---

@app.post("/api/quizzes/", response_model=QuizResponse, status_code=201)
async def create_quiz(
    quiz: QuizCreate, 
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_optional_user)
):
    # If authenticated, associate quiz with user
    if current_user:
        db_quiz = QuizDB(name=quiz.name, time_limit_minutes=quiz.time_limit_minutes, created_by_user_id=current_user.id)
    else:
        db_quiz = QuizDB(name=quiz.name, time_limit_minutes=quiz.time_limit_minutes)
    db.add(db_quiz)
    try:
        db.commit()
        db.refresh(db_quiz)
        return db_quiz
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Quiz name already exists.")
    except Exception as e:
        print(f"An error occurred during quiz creation: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/api/quizzes/", response_model=List[QuizResponse])
async def read_quizzes(db: Session = Depends(get_db)):
    quizzes_db = db.query(QuizDB).all()
    return quizzes_db

@app.get("/api/quizzes/{quiz_id}", response_model=QuizResponse)
async def read_quiz(quiz_id: int = Path(..., title="The ID of the quiz to get"), db: Session = Depends(get_db)):
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return db_quiz

# --- RC Passage Management Endpoints ---
@app.post("/api/rc_passages/", response_model=RCPassageResponse, status_code=201)
async def create_rc_passage(rc_passage: RCPassageCreate, db: Session = Depends(get_db)):
    db_rc_passage = RCPassageDB(
        title=rc_passage.title,
        passage_text=rc_passage.passage_text
    )
    db.add(db_rc_passage)
    try:
        db.commit()
        db.refresh(db_rc_passage)
        return db_rc_passage
    except Exception as e:
        print(f"An error occurred during RC passage creation: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/api/rc_passages/", response_model=List[RCPassageResponse])
async def read_rc_passages(db: Session = Depends(get_db)):
    rc_passages_db = db.query(RCPassageDB).all()
    return rc_passages_db

@app.get("/api/rc_passages/{rc_id}", response_model=RCPassageResponse)
async def read_rc_passage(rc_id: int = Path(..., title="The ID of the RC passage to get"), db: Session = Depends(get_db)):
    db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
    if db_rc_passage is None:
        raise HTTPException(status_code=404, detail="RC Passage not found")
    return db_rc_passage

@app.put("/api/rc_passages/{rc_id}", response_model=RCPassageResponse)
async def update_rc_passage(rc_id: int, rc_passage: RCPassageCreate, db: Session = Depends(get_db)):
    db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
    if db_rc_passage is None:
        raise HTTPException(status_code=404, detail="RC Passage not found")
    db_rc_passage.title = rc_passage.title
    db_rc_passage.passage_text = rc_passage.passage_text
    db.commit()
    db.refresh(db_rc_passage)
    return db_rc_passage

@app.delete("/api/rc_passages/{rc_id}", status_code=204)
async def delete_rc_passage(rc_id: int = Path(..., title="The ID of the RC passage to delete"), db: Session = Depends(get_db)):
    db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
    if db_rc_passage is None:
        raise HTTPException(status_code=404, detail="RC Passage not found")
    questions_to_unlink = db.query(QuestionDB).filter(QuestionDB.rc_id == rc_id).all()
    for question in questions_to_unlink:
        question.rc_id = None
    db.delete(db_rc_passage)
    db.commit()
    return

# --- Question Management Endpoints (Linked to Quizzes) ---

@app.get("/api/questions/{question_id}", response_model=QuestionResponse)
async def read_question(question_id: int = Path(..., title="The ID of the question to get"), db: Session = Depends(get_db)):
    db_question = db.query(QuestionDB).options(
        joinedload(QuestionDB.rc_passage)
    ).filter(QuestionDB.id == question_id).first()
    if db_question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    rc_passage_response = None
    if db_question.rc_passage:
        rc_passage_response = RCPassageResponse.model_validate(db_question.rc_passage)    
    return QuestionResponse(
        id=db_question.id,
        quiz_id=db_question.quiz_id,
        rc_id=db_question.rc_id,
        rc_passage=rc_passage_response,
        questionText=db_question.question_text,
        options=json.loads(db_question.options_json),
        correctAnswer=db_question.correct_answer,
        answerExplanation=db_question.answer_explanation,
        image=db_question.image,
        difficulty=db_question.difficulty,
        question_type=db_question.question_type,
        subsection=db_question.subsection
    )

@app.post("/api/quizzes/{quiz_id}/questions/", response_model=QuestionResponse, status_code=201)
async def create_question_for_quiz(
    quiz_id: int = Path(..., title="The ID of the quiz to add the question to"),
    question: str = Form(...),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    try:
        question_data = json.loads(question)
        question_text = question_data.get("questionText")
        options = question_data.get("options")
        correct_answer = question_data.get("correctAnswer")
        answer_explanation = question_data.get("answerExplanation")
        difficulty = question_data.get("difficulty")
        rc_id = question_data.get("rc_id")
        question_type = question_data.get("question_type")
        subsection = question_data.get("subsection")
        image_filename_from_data = question_data.get("image")

        if not all([question_text, options, correct_answer, difficulty, question_type]):
             raise HTTPException(status_code=400, detail="Missing required question data (text, options, answer, difficulty, type).")
        valid_types = ["Quant", "Verbal", "Data Insights"]
        if question_type not in valid_types:
             raise HTTPException(status_code=400, detail=f"Invalid question_type: {question_type}. Must be one of {valid_types}")
        if question_type == "Verbal":
             valid_subsections = ["RC", "CR"]
             if subsection not in valid_subsections:
                  raise HTTPException(status_code=400, detail=f"Invalid subsection for Verbal type: {subsection}. Must be one of {valid_subsections}")
             if subsection == "RC" and rc_id is None:
                  raise HTTPException(status_code=400, detail="RC questions must be linked to an RC passage.")
             if subsection == "CR" and rc_id is not None:
                  raise HTTPException(status_code=400, detail="CR questions cannot be linked to an RC passage.")
        elif subsection is not None:
             raise HTTPException(status_code=400, detail=f"Subsection must be null for question_type {question_type}.")
        if question_type in ["Quant", "Data Insights"] and rc_id is not None:
             raise HTTPException(status_code=400, detail=f"RC Passage link must be null for question_type {question_type}.")
        if rc_id is not None:
            db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
            if db_rc_passage is None:
                raise HTTPException(status_code=404, detail=f"RC Passage with ID {rc_id} not found.")
        image_filename = None
        if image_file:
            file_location = os.path.join(IMAGES_DIR, image_file.filename)
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(image_file.file, buffer)
            image_filename = image_file.filename
        elif image_filename_from_data:
             image_filename = image_filename_from_data
        db_question = QuestionDB(
            quiz_id=quiz_id,
            rc_id=rc_id,
            question_text=question_text,
            options_json=json.dumps(options),
            correct_answer=correct_answer,
            answer_explanation=answer_explanation,
            image=image_filename,
            difficulty=difficulty,
            question_type=question_type,
            subsection=subsection
        )
        db.add(db_question)
        try:
            db.commit()
            db.refresh(db_question)
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Question could not be added due to a database error.")
        rc_passage_response = None
        if db_question.rc_id:
             db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == db_question.rc_id).first()
             if db_rc_passage:
                  rc_passage_response = RCPassageResponse.model_validate(db_rc_passage)
        return QuestionResponse(
            id=db_question.id,
            quiz_id=db_question.quiz_id,
            rc_id=db_question.rc_id,
            rc_passage=rc_passage_response,
            questionText=db_question.question_text,
            options=json.loads(db_question.options_json),
            correctAnswer=db_question.correct_answer,
            answerExplanation=db_question.answer_explanation,
            image=db_question.image,
            difficulty=db_question.difficulty,
            question_type=db_question.question_type,
            subsection=db_question.subsection
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for question data.")
    except Exception as e:
        print(f"An error occurred during question creation: {e}")
        if "Missing required question data" in str(e) or "Invalid" in str(e):
             raise
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

# --- Caching ---
from fastapi import Response
from cachetools import TTLCache

# Cache for quiz questions (10 minute TTL, max 100 quizzes)
quiz_question_cache = TTLCache(maxsize=100, ttl=600)

@app.get("/api/quizzes/{quiz_id}/questions/", response_model=List[QuestionResponse])
async def read_questions_for_quiz(
    quiz_id: int = Path(..., title="The ID of the quiz to get questions for"),
    response: Response = None,
    db: Session = Depends(get_db)
):
    # Check cache first
    if quiz_id in quiz_question_cache:
        response.headers["X-Cache"] = "HIT"
        return quiz_question_cache[quiz_id]

    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    questions_db = db.query(QuestionDB).options(
        joinedload(QuestionDB.rc_passage)
    ).filter(QuestionDB.quiz_id == quiz_id).all()
    response_list = []
    for q in questions_db:
        rc_passage_response = None
        if q.rc_passage:
            rc_passage_response = RCPassageResponse.model_validate(q.rc_passage)
        response_list.append(QuestionResponse(
            id=q.id,
            quiz_id=q.quiz_id,
            rc_id=q.rc_id,
            rc_passage=rc_passage_response,
            questionText=q.question_text,
            options=json.loads(q.options_json),
            correctAnswer=q.correct_answer,
            image=q.image,
            difficulty=q.difficulty,
            question_type=q.question_type,
            subsection=q.subsection,
            answerExplanation=q.answer_explanation
        ))

    # Add to cache
    quiz_question_cache[quiz_id] = response_list
    response.headers["X-Cache"] = "MISS"

    return response_list

@app.delete("/api/questions/{question_id}", status_code=204)
async def delete_question(question_id: int, db: Session = Depends(get_db)):
    db_question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
    if db_question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if db_question.image:
        image_path = os.path.join(IMAGES_DIR, db_question.image)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"Deleted image file: {image_path}")
            except OSError as e:
                print(f"Error deleting image file {image_path}: {e}")
    db.delete(db_question)
    db.commit()
    return

@app.put("/api/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: int,
    question: str = Form(...),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    db_question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
    if db_question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    try:
        question_data = json.loads(question)
        question_text = question_data.get("questionText")
        options = question_data.get("options")
        correct_answer = question_data.get("correctAnswer")
        answer_explanation = question_data.get("answerExplanation")
        difficulty = question_data.get("difficulty")
        rc_id = question_data.get("rc_id")
        question_type = question_data.get("question_type")
        subsection = question_data.get("subsection")

        if not all([question_text, options, correct_answer, difficulty, question_type]):
            raise HTTPException(status_code=400, detail="Missing required question data (text, options, answer, difficulty, type).")
        valid_types = ["Quant", "Verbal", "Data Insights"]
        if question_type not in valid_types:
             raise HTTPException(status_code=400, detail=f"Invalid question_type: {question_type}. Must be one of {valid_types}")
        if question_type == "Verbal":
             valid_subsections = ["RC", "CR"]
             if subsection not in valid_subsections:
                  raise HTTPException(status_code=400, detail=f"Invalid subsection for Verbal type: {subsection}. Must be one of {valid_subsections}")
             if subsection == "RC" and rc_id is None:
                  raise HTTPException(status_code=400, detail="RC questions must be linked to an RC passage.")
             if subsection == "CR" and rc_id is not None:
                  raise HTTPException(status_code=400, detail="CR questions cannot be linked to an RC passage.")
        elif subsection is not None:
             raise HTTPException(status_code=400, detail=f"Subsection must be null for question_type {question_type}.")
        if question_type in ["Quant", "Data Insights"] and rc_id is not None:
             raise HTTPException(status_code=400, detail=f"RC Passage link must be null for question_type {question_type}.")
        if rc_id is not None:
             db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
             if db_rc_passage is None:
                 raise HTTPException(status_code=404, detail=f"RC Passage with ID {rc_id} not found.")
        if image_file:
            if db_question.image:
                old_image_path = os.path.join(IMAGES_DIR, db_question.image)
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except OSError:
                        pass
            file_location = os.path.join(IMAGES_DIR, image_file.filename)
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(image_file.file, buffer)
            db_question.image = image_file.filename
        db_question.question_text = question_text
        db_question.options_json = json.dumps(options)
        db_question.correct_answer = correct_answer
        db_question.answer_explanation = answer_explanation
        db_question.difficulty = difficulty
        db_question.rc_id = rc_id
        db_question.question_type = question_type
        db_question.subsection = subsection
        db.commit()
        db.refresh(db_question)
        rc_passage_response = None
        if db_question.rc_id:
             db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == db_question.rc_id).first()
             if db_rc_passage:
                  rc_passage_response = RCPassageResponse.model_validate(db_rc_passage)
        return QuestionResponse(
            id=db_question.id,
            quiz_id=db_question.quiz_id,
            rc_id=db_question.rc_id,
            rc_passage=rc_passage_response,
            questionText=db_question.question_text,
            options=json.loads(db_question.options_json),
            correctAnswer=db_question.correct_answer,
            answerExplanation=db_question.answer_explanation,
            image=db_question.image,
            difficulty=db_question.difficulty,
            question_type=db_question.question_type,
            subsection=db_question.subsection
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for question data.")
    except Exception as e:
        print(f"An error occurred during question update: {e}")
        if "Missing required question data" in str(e) or "Invalid" in str(e):
             raise
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.delete("/api/quizzes/{quiz_id}", status_code=204)
async def delete_quiz(quiz_id: int = Path(..., title="The ID of the quiz to delete"), db: Session = Depends(get_db)):
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    rc_passage_ids = set()
    for question in db_quiz.questions:
        if question.rc_id is not None:
            rc_passage_ids.add(question.rc_id)
    exclusive_rc_passage_ids = []
    for rc_id in rc_passage_ids:
        other_quiz_questions = db.query(QuestionDB).filter(
            QuestionDB.rc_id == rc_id,
            QuestionDB.quiz_id != quiz_id
        ).first()
        if other_quiz_questions is None:
            exclusive_rc_passage_ids.append(rc_id)
    for question in db_quiz.questions:
         if question.image:
             image_path = os.path.join(IMAGES_DIR, question.image)
             if os.path.exists(image_path):
                 try:
                     os.remove(image_path)
                     print(f"Deleted image file: {image_path}")
                 except OSError as e:
                     print(f"Error deleting image file {image_path}: {e}")
    db.delete(db_quiz)
    db.commit()
    for rc_id in exclusive_rc_passage_ids:
        db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
        if db_rc_passage:
            db.delete(db_rc_passage)
            print(f"Deleted RC passage {rc_id} that was exclusively used by quiz {quiz_id}")
    if exclusive_rc_passage_ids:
        db.commit()
    return

# --- Performance Endpoints (Linked to Quizzes) ---

@app.post("/api/performance/", status_code=201)
async def create_performance_record(performance_data: PerformanceCreate, db: Session = Depends(get_db)):
    db_quiz = db.query(QuizDB).filter(QuizDB.id == performance_data.quizId).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    db_performance = PerformanceDB(
        quiz_id=performance_data.quizId,
        total_questions=performance_data.totalQuestions,
        correct_answers=performance_data.correctAnswers,
        time_taken_seconds=performance_data.timeTakenSeconds,
        timestamp=datetime.datetime.utcnow(),
    )
    db.add(db_performance)
    db.commit()
    db.refresh(db_performance)

    for result in performance_data.detailedResults:
        db_detailed_result = DetailedResultDB(
            performance_id=db_performance.id,
            question_id=result.questionId,
            correct=result.correct,
            user_answer=result.userAnswer,
            time_spent=result.timeSpent
        )
        db.add(db_detailed_result)
    db.add(db_performance)
    try:
        db.commit()
        db.refresh(db_performance)
        return {"message": "Performance record saved successfully", "id": db_performance.id}
    except Exception as e:
        db.rollback()
        print(f"An error occurred during performance record creation: {e}")
        raise HTTPException(status_code=500, detail="Failed to save performance record.")

@app.get("/api/performance/", response_model=List[PerformanceResponse])
async def read_performance_records(quiz_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(PerformanceDB).options(joinedload(PerformanceDB.detailed_results))
    if quiz_id is not None:
        db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
        if db_quiz is None:
            raise HTTPException(status_code=404, detail="Quiz not found")
        query = query.filter(PerformanceDB.quiz_id == quiz_id)
    performance_records_db = query.order_by(PerformanceDB.timestamp).all()

    response = []
    for rec in performance_records_db:
        detailed_results = []
        for result in rec.detailed_results:
            question = result.question
            detailed_results.append(DetailedQuestionResult(
                questionId=result.question_id,
                correct=result.correct,
                difficulty=question.difficulty,
                userAnswer=result.user_answer,
                correctAnswer=question.correct_answer,
                questionText=question.question_text,
                options=json.loads(question.options_json),
                question_type=question.question_type,
                subsection=question.subsection,
                timeSpent=result.time_spent,
                answerExplanation=question.answer_explanation
            ))
        response.append(PerformanceResponse(
            id=rec.id,
            quizId=rec.quiz_id,
            timestamp=rec.timestamp,
            totalQuestions=rec.total_questions,
            correctAnswers=rec.correct_answers,
            timeTakenSeconds=rec.time_taken_seconds,
            detailedResults=detailed_results
        ))
    return response

@app.get("/api/performance/{performance_id}", response_model=PerformanceResponse)
async def get_performance_record(
    performance_id: int = Path(..., title="The ID of the performance record to retrieve"),
    db: Session = Depends(get_db)
):
    performance_record = db.query(PerformanceDB).filter(PerformanceDB.id == performance_id).first()
    if performance_record is None:
        raise HTTPException(status_code=404, detail="Performance record not found")
    detailed_results = []
    for result in performance_record.detailed_results:
        question = result.question
        detailed_results.append(DetailedQuestionResult(
            questionId=result.question_id,
            correct=result.correct,
            difficulty=question.difficulty,
            userAnswer=result.user_answer,
            correctAnswer=question.correct_answer,
            questionText=question.question_text,
            options=json.loads(question.options_json),
            question_type=question.question_type,
            subsection=question.subsection,
            timeSpent=result.time_spent,
            answerExplanation=question.answer_explanation
        ))
    return PerformanceResponse(
        id=performance_record.id,
        quizId=performance_record.quiz_id,
        timestamp=performance_record.timestamp,
        totalQuestions=performance_record.total_questions,
        correctAnswers=performance_record.correct_answers,
        timeTakenSeconds=performance_record.time_taken_seconds,
        detailedResults=detailed_results
    )

# NEW ENDPOINT FOR DELETING A PERFORMANCE RECORD
@app.delete("/api/performance/{performance_id}", status_code=204)
async def delete_performance_record(
    performance_id: int = Path(..., title="The ID of the performance record to delete"),
    db: Session = Depends(get_db)
):
    """
    Deletes a specific performance record by its ID.
    Also deletes any associated user explanations for that performance record.
    """
    # Find the performance record
    db_performance = db.query(PerformanceDB).filter(PerformanceDB.id == performance_id).first()

    # If not found, raise a 404 error
    if db_performance is None:
        raise HTTPException(status_code=404, detail="Performance record not found")

    # Delete associated user explanations first (due to cascade on PerformanceDB this might be redundant, but explicit is good)
    # If UserExplanationDB.performance relationship has cascade="all, delete-orphan", this step is handled automatically.
    # However, to be absolutely sure, we can do it manually or ensure the cascade is correctly set.
    # Assuming cascade="all, delete-orphan" is set on PerformanceDB.user_explanations relationship.

    # Delete the performance record
    db.delete(db_performance)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error deleting performance record {performance_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not delete performance record.")
    
    return # Returns 204 No Content on successful deletion


@app.get("/api/performance/{performance_id}/detailed-review", response_model=List[DetailedPerformanceReview])
async def get_detailed_performance_review(
    performance_id: int = Path(..., title="The ID of the performance record to get detailed review for"),
    db: Session = Depends(get_db)
):
    performance_record = db.query(PerformanceDB).filter(PerformanceDB.id == performance_id).first()
    if performance_record is None:
        raise HTTPException(status_code=404, detail="Performance record not found")
    performance_record = db.query(PerformanceDB).options(
        joinedload(PerformanceDB.detailed_results).joinedload(DetailedResultDB.question).joinedload(QuestionDB.rc_passage),
        joinedload(PerformanceDB.user_explanations)
    ).filter(PerformanceDB.id == performance_id).first()

    if performance_record is None:
        raise HTTPException(status_code=404, detail="Performance record not found")

    review_items = []
    for result in performance_record.detailed_results:
        question = result.question
        rc_passage_data = None
        if question.rc_passage:
            rc_passage_data = RCPassageResponse.from_orm(question.rc_passage)

        user_explanation = next((exp for exp in performance_record.user_explanations if exp.question_id == result.question_id), None)

        review_item = DetailedPerformanceReview(
            questionId=result.question_id,
            correct=result.correct,
            userAnswer=result.user_answer,
            correctAnswer=question.correct_answer,
            questionText=question.question_text,
            options=json.loads(question.options_json),
            difficulty=question.difficulty,
            question_type=question.question_type,
            subsection=question.subsection,
            timeSpent=result.time_spent,
            answerExplanation=question.answer_explanation,
            rc_passage=rc_passage_data,
            userExplanation=user_explanation.explanation_text if user_explanation else None
        )
        review_items.append(review_item)
    return review_items

@app.get("/api/performance/summary/{quiz_id}")
async def get_performance_summary(
    quiz_id: int = Path(..., title="The ID of the quiz to get performance summary for"),
    db: Session = Depends(get_db)
):
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    performance_records = db.query(PerformanceDB).filter(PerformanceDB.quiz_id == quiz_id).all()
    if not performance_records:
        return {
            "quizId": quiz_id,
            "quizName": db_quiz.name,
            "totalAttempts": 0,
            "summary": "No performance data available for this quiz."
        }
    total_attempts = len(performance_records)
    total_questions_attempted = sum(record.total_questions for record in performance_records)
    total_correct_answers = sum(record.correct_answers for record in performance_records)
    average_score = (total_correct_answers / total_questions_attempted * 100) if total_questions_attempted > 0 else 0
    average_time = sum(record.time_taken_seconds for record in performance_records) / total_attempts
    type_stats = {}
    difficulty_stats = {}
    common_mistakes = []
    for record in performance_records:
        for result in record.detailed_results:
            question = result.question
            q_type = question.question_type
            difficulty = question.difficulty
            correct = result.correct
            if q_type not in type_stats:
                type_stats[q_type] = {"total": 0, "correct": 0}
            type_stats[q_type]["total"] += 1
            if correct:
                type_stats[q_type]["correct"] += 1
            if difficulty not in difficulty_stats:
                difficulty_stats[difficulty] = {"total": 0, "correct": 0}
            difficulty_stats[difficulty]["total"] += 1
            if correct:
                difficulty_stats[difficulty]["correct"] += 1
            if not correct:
                mistake_entry = {
                    "questionId": result.question_id,
                    "questionText": question.question_text[:100] + "...",
                    "userAnswer": result.user_answer,
                    "correctAnswer": question.correct_answer,
                    "question_type": q_type,
                    "difficulty": difficulty
                }
                common_mistakes.append(mistake_entry)
    for stats in type_stats.values():
        stats["percentage"] = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
    for stats in difficulty_stats.values():
        stats["percentage"] = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
    return {
        "quizId": quiz_id,
        "quizName": db_quiz.name,
        "totalAttempts": total_attempts,
        "averageScore": round(average_score, 2),
        "averageTimeMinutes": round(average_time / 60, 2),
        "totalQuestionsAttempted": total_questions_attempted,
        "totalCorrectAnswers": total_correct_answers,
        "performanceByType": type_stats,
        "performanceByDifficulty": difficulty_stats,
        "commonMistakes": common_mistakes[:10],
        "recentPerformances": [
            {
                "id": record.id,
                "timestamp": record.timestamp.isoformat(),
                "score": f"{record.correct_answers}/{record.total_questions}",
                "percentage": round((record.correct_answers / record.total_questions * 100), 2) if record.total_questions > 0 else 0,
                "timeMinutes": round(record.time_taken_seconds / 60, 2)
            }
            for record in sorted(performance_records, key=lambda x: x.timestamp, reverse=True)[:5]
        ]
    }

@app.post("/api/quizzes/{quiz_id}/questions/bulk/")
async def bulk_add_questions(quiz_id: int, questions: List[BulkQuestionCreate], db: Session = Depends(get_db)):
    # Debug logging
    print(f"Bulk upload request for quiz_id: {quiz_id}")
    print(f"Number of questions received: {len(questions)}")
    
    # Check if quiz exists
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        print(f"Quiz not found for ID: {quiz_id}")
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    print(f"Quiz found: {db_quiz.name}")
    
    count = 0
    try:
        for i, q in enumerate(questions):
            print(f"Processing question {i+1}: {q.questionText[:50]}...")
            
            # Validate question type
            valid_types = ["Quant", "Verbal", "Data Insights"]
            if q.question_type not in valid_types:
                 raise HTTPException(status_code=400, detail=f"Invalid question_type in bulk data: {q.question_type}. Must be one of {valid_types}")
            
            # Validate Verbal questions
            if q.question_type == "Verbal":
                 valid_subsections = ["RC", "CR"]
                 if q.subsection not in valid_subsections:
                      raise HTTPException(status_code=400, detail=f"Invalid subsection for Verbal type in bulk data: {q.subsection}. Must be one of {valid_subsections}")
                 if q.subsection == "RC" and q.rc_id is None:
                      raise HTTPException(status_code=400, detail="RC questions in bulk data must be linked to an RC passage.")
                 if q.subsection == "CR" and q.rc_id is not None:
                      raise HTTPException(status_code=400, detail="CR questions in bulk data cannot be linked to an RC passage.")
            elif q.subsection is not None:
                 raise HTTPException(status_code=400, detail=f"Subsection in bulk data must be null for question_type {q.question_type}.")
            
            # Validate RC passage linking
            if q.question_type in ["Quant", "Data Insights"] and q.rc_id is not None:
                 raise HTTPException(status_code=400, detail=f"RC Passage link in bulk data must be null for question_type {q.question_type}.")
            
            # Check if RC passage exists when referenced
            if q.rc_id is not None:
                db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == q.rc_id).first()
                if db_rc_passage is None:
                    raise HTTPException(status_code=404, detail=f"RC Passage with ID {q.rc_id} not found for a question in the bulk upload.")
            
            # Create question
            db_question = QuestionDB(
                quiz_id=quiz_id,
                rc_id=q.rc_id,
                question_text=q.questionText,
                options_json=json.dumps(q.options),
                correct_answer=q.correctAnswer,
                answer_explanation=q.answerExplanation,
                image=None,
                difficulty=q.difficulty,
                question_type=q.question_type,
                subsection=q.subsection
            )
            db.add(db_question)
            count += 1
        
        # Commit all changes
        db.commit()
        print(f"Successfully added {count} questions to quiz {quiz_id}")
        return {"message": f"{count} questions added to quiz {quiz_id}."}
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are
        db.rollback()
        raise
    except Exception as e:
        # Handle unexpected database errors
        db.rollback()
        print(f"Database error during bulk upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error during bulk upload: {str(e)}")

# --- User Explanation Endpoints ---

@app.post("/api/performance/{performance_id}/explanations/", response_model=UserExplanationResponse, status_code=201)
async def create_user_explanation(
    performance_id: int,
    explanation: UserExplanationCreate,
    db: Session = Depends(get_db)
):
    performance = db.query(PerformanceDB).filter(PerformanceDB.id == performance_id).first()
    if not performance:
        raise HTTPException(status_code=404, detail="Performance record not found")
    question = db.query(QuestionDB).filter(QuestionDB.id == explanation.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    existing_explanation = db.query(UserExplanationDB).filter(
        UserExplanationDB.performance_id == performance_id,
        UserExplanationDB.question_id == explanation.question_id
    ).first()
    if existing_explanation:
        existing_explanation.explanation_text = explanation.explanation_text
        existing_explanation.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(existing_explanation)
        return existing_explanation
    else:
        db_explanation = UserExplanationDB(
            performance_id=performance_id,
            question_id=explanation.question_id,
            explanation_text=explanation.explanation_text
        )
        db.add(db_explanation)
        db.commit()
        db.refresh(db_explanation)
        return db_explanation

@app.get("/api/performance/{performance_id}/explanations/", response_model=List[UserExplanationResponse])
async def get_user_explanations(
    performance_id: int,
    db: Session = Depends(get_db)
):
    performance = db.query(PerformanceDB).filter(PerformanceDB.id == performance_id).first()
    if not performance:
        raise HTTPException(status_code=404, detail="Performance record not found")
    explanations = db.query(UserExplanationDB).filter(
        UserExplanationDB.performance_id == performance_id
    ).all()
    return explanations

@app.get("/api/performance/{performance_id}/explanations/{question_id}", response_model=UserExplanationResponse)
async def get_user_explanation(
    performance_id: int,
    question_id: int,
    db: Session = Depends(get_db)
):
    explanation = db.query(UserExplanationDB).filter(
        UserExplanationDB.performance_id == performance_id,
        UserExplanationDB.question_id == question_id
    ).first()
    if not explanation:
        raise HTTPException(status_code=404, detail="User explanation not found")
    return explanation

@app.put("/api/performance/{performance_id}/explanations/{question_id}", response_model=UserExplanationResponse)
async def update_user_explanation(
    performance_id: int,
    question_id: int,
    explanation_update: UserExplanationUpdate,
    db: Session = Depends(get_db)
):
    explanation = db.query(UserExplanationDB).filter(
        UserExplanationDB.performance_id == performance_id,
        UserExplanationDB.question_id == question_id
    ).first()
    if not explanation:
        raise HTTPException(status_code=404, detail="User explanation not found")
    explanation.explanation_text = explanation_update.explanation_text
    explanation.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(explanation)
    return explanation

@app.delete("/api/performance/{performance_id}/explanations/{question_id}", status_code=204)
async def delete_user_explanation(
    performance_id: int,
    question_id: int,
    db: Session = Depends(get_db)
):
    explanation = db.query(UserExplanationDB).filter(
        UserExplanationDB.performance_id == performance_id,
        UserExplanationDB.question_id == question_id
    ).first()
    if not explanation:
        raise HTTPException(status_code=404, detail="User explanation not found")
    db.delete(explanation)
    db.commit()


# --- NEW Pydantic Models for AI Chat ---
class AIChatPart(BaseModel):
    text: str

class AIChatMessage(BaseModel):
    role: str
    parts: List[AIChatPart]

class AIAnalysisRequest(BaseModel):
    history: List[AIChatMessage]
    quiz_id: Optional[int] = None # Allow filtering data by quiz
    gemini_api_key: Optional[str] = None # API key can be provided from frontend


# --- Helper function to get performance context from DB ---
def get_performance_context_from_db(db: Session, quiz_id: Optional[int] = None):
    query = db.query(PerformanceDB).options(joinedload(PerformanceDB.quiz))
    if quiz_id:
        query = query.filter(PerformanceDB.quiz_id == quiz_id)
    
    records = query.all()
    if not records:
        return "{}" # Return empty JSON if no records found

    difficulty_scores = {"easy": {"correct": 0, "total": 0}, "medium": {"correct": 0, "total": 0}, "hard": {"correct": 0, "total": 0}}
    question_type_data = {}
    verbal_subsection_data = {}

    for record in records:
        if record.detailed_results_json:
            try:
                detailed_results = json.loads(record.detailed_results_json)
                for q in detailed_results:
                    diff = q.get("difficulty", "unknown").lower()
                    if diff not in difficulty_scores: continue
                    difficulty_scores[diff]["total"] += 1
                    if q.get("correct"): difficulty_scores[diff]["correct"] += 1

                    q_type = q.get("question_type", "Unknown")
                    if q_type not in question_type_data: question_type_data[q_type] = {"correct": 0, "total": 0}
                    question_type_data[q_type]["total"] += 1
                    if q.get("correct"): question_type_data[q_type]["correct"] += 1

                    if q_type == "Verbal":
                        sub = q.get("subsection", "Unknown")
                        if sub not in verbal_subsection_data: verbal_subsection_data[sub] = {"correct": 0, "total": 0}
                        verbal_subsection_data[sub]["total"] += 1
                        if q.get("correct"): verbal_subsection_data[sub]["correct"] += 1
            except (json.JSONDecodeError, TypeError):
                continue

    total_correct = sum(r.correct_answers for r in records)
    total_questions = sum(r.total_questions for r in records)
    overall_accuracy = f"{(total_correct / total_questions * 100):.1f}%" if total_questions > 0 else "N/A"

    context = {
        "summary": {
            "totalQuizzesTaken": len(set(r.quiz_id for r in records)),
            "totalAttempts": len(records),
            "overallAccuracy": overall_accuracy,
            "totalQuestionsAttempted": total_questions,
        },
        "accuracyByDifficulty": {k: f"{(v['correct'] / v['total'] * 100):.1f}%" if v['total'] > 0 else "N/A" for k, v in difficulty_scores.items()},
        "accuracyByQuestionType": {k: f"{(v['correct'] / v['total'] * 100):.1f}%" if v['total'] > 0 else "N/A" for k, v in question_type_data.items()},
        "verbalSubsections": {k: f"{(v['correct'] / v['total'] * 100):.1f}%" if v['total'] > 0 else "N/A" for k, v in verbal_subsection_data.items()} if verbal_subsection_data else None,
        "recentPerformance": [
            {
                "quizName": r.quiz.name,
                "score": f"{r.correct_answers}/{r.total_questions}",
                "date": r.timestamp.strftime("%Y-%m-%d")
            } for r in sorted(records, key=lambda r: r.timestamp, reverse=True)[:5]
        ]
    }
    return json.dumps(context, indent=2)


async def call_gemini_with_retry(payload: Dict[str, Any], gemini_api_key: str = None, max_retries: int = 3) -> Dict[str, Any]:
    """
    Call Gemini API with proper rate limiting and retry logic.
    Based on official Gemini documentation best practices.
    
    Uses the provided API key or falls back to the environment variable if available.
    """
    # Use provided API key or environment variable as fallback
    api_key = gemini_api_key or GOOGLE_API_KEY
    
    if not api_key:
        raise HTTPException(status_code=400, detail="No Gemini API key provided. Please set one in your profile or provide it in the request.")
        
    # Construct the full URL with the API key
    api_url = f"{GEMINI_API_URL_BASE}?key={api_key}"
    
    # Apply rate limiting first
    await gemini_rate_limiter.acquire()
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    api_url, 
                    json=payload, 
                    timeout=httpx.Timeout(60.0)
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limit exceeded
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt * 2 seconds
                    wait_time = (2 ** attempt) * 2
                    print(f"Rate limited by Gemini API. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise HTTPException(status_code=429, detail="Gemini API rate limit exceeded. Please try again later.")
            
            elif e.response.status_code >= 500:  # Server errors are retryable
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"Gemini API server error {e.response.status_code}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise HTTPException(status_code=502, detail=f"Gemini API server error: {e.response.text}")
            
            else:  # Client errors (400-499) are not retryable
                error_text = e.response.text
                print(f"Gemini API client error {e.response.status_code}: {error_text}")
                raise HTTPException(status_code=502, detail=f"Gemini API error: {error_text}")
        
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                print(f"Gemini API timeout. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            else:
                raise HTTPException(status_code=504, detail="Gemini API timeout after retries")
        
        except Exception as e:
            print(f"Unexpected error calling Gemini API: {e}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                await asyncio.sleep(wait_time)
                continue
            else:
                raise HTTPException(status_code=500, detail="Internal server error during AI analysis")


# --- NEW AI Analysis Endpoint ---
@app.post("/api/ai/analyze")
async def analyze_performance(request: AIAnalysisRequest, db: Session = Depends(get_db)):
    """
    This endpoint orchestrates a conversation with the Gemini API,
    using tools to fetch live database data as needed.
    Implements proper rate limiting and error handling for Gemini free tier.
    """
    system_prompt_text = f"""
        You are an expert GMAT tutor and data analyst with deep expertise in standardized test preparation and performance analysis.
        
        ## Your Role and Expertise:
        - **Personal GMAT Tutor**: Provide personalized, actionable insights based on student performance data
        - **Data Analyst**: Interpret performance patterns, trends, and statistical insights from quiz data
        - **Study Coach**: Create targeted study plans and recommend specific improvement strategies
        - **Test Strategy Expert**: Analyze timing, question types, and difficulty patterns
        
        ## Context:
        - Today's date: {datetime.date.today().strftime('%B %d, %Y')}
        - You have access to comprehensive GMAT Focus Edition performance data through specialized tools
        - The student is preparing for the GMAT Focus Edition and wants personalized insights ALSO MASTER EACH AND EVERY TOPIC OF GMAT FOCUS EDITION and achieve top 1 percentile results. 
        - You need to make sure student achieves a top 1% score on the GMAT Focus Edition, which requires mastery of all topics and question types.
        
        ## Available Data Sources (via tools):
        - Overall performance summaries and statistics
        - Detailed question-by-question results for recent quiz attempts
        - Performance breakdowns by question type (Verbal, Quantitative, Data Insights)
        - Difficulty level analysis (Easy, Medium, Hard)
        - Time management and pacing data
        - Historical performance trends and chronological sorting
        - Incorrect answer patterns and user explanations
        - Quiz content and question details
        
        ## Tool Selection Guidelines:
        - **For recent/latest quiz analysis**: Use `analyze_latest_quiz_detailed` for comprehensive question-by-question breakdown
        - **For progress over time**: Use `get_quizzes_sorted_by_date` to compare oldest vs newest performance
        - **For overall statistics**: Use `get_performance_summary` for aggregate data across all attempts
        - **For specific mistakes**: Use `get_most_recent_incorrect_answers` for detailed error analysis
        - **For quiz content**: Use `get_quiz_questions` when you need to see actual question text
        
        ## Response Guidelines:
        1. **Be Specific & Actionable**: Always provide concrete, implementable recommendations
        2. **Use Data-Driven Insights**: Base all conclusions on actual performance data
        3. **Personalize**: Tailor advice to the student's specific strengths and weaknesses
        4. **Structure Clearly**: Use headers, bullet points, and organized sections
        5. **Be Encouraging**: Highlight progress and strengths while addressing weaknesses
        6. **Focus on Improvement**: Every insight should lead to actionable next steps
        7. **Use Statistics**: Include specific numbers, percentages, and trends when available
        8. **Tell top 1% Short tricks**: Provide advanced strategies that can significantly boost performance, essential short tricks.
        9. **Use Tables**: When comparing data, use tables for clarity

        ## Analysis Framework:
        When providing analysis, consider:
        - **Performance Patterns**: What trends emerge across attempts?
        - **Content Mastery**: Which topics/question types need work?
        - **Test Strategy**: How can timing and approach be optimized?
        - **Learning Progression**: What does the improvement trajectory look like?
        - **Target Areas**: Which areas will yield the highest score improvements?
        
        ## Output Format:
        - Use clear HTML formatting with headers and bullet points
        - Use Latex formatting for mathematical equations. Be aware of the questions that have $ sign for those use alternative latex syntax like \(...\) to make sure everything appears correctly
        - Include specific statistics and percentages when available
        - Provide numbered action items for recommendations
        - Use tables for comparative data when helpful
        - Highlight key insights with **bold text**
        
        Always gather sufficient data using the available tools before providing your analysis. If you need specific data to answer a question, use the appropriate tools to fetch that information first.
    """

    # Construct the conversation history for the API
    history_for_api = [msg.model_dump() for msg in request.history]

    # Ensure there's at least one message in history_for_api for the initial call
    if not history_for_api:
        # Default comprehensive analysis prompt
        history_for_api.append({
            "role": "user", 
            "parts": [{
                "text": "Please provide a comprehensive analysis of my GMAT performance. I'd like to understand my strengths, weaknesses, and get specific recommendations for improvement. Please analyse my accuracy by question type and difficulty, review my recent performance trends, and identify the most important areas I should focus on studying."
            }]
        })

    max_turns = 10  # Prevent infinite loops
    turn_count = 0

    # The conversation may take multiple "turns" if the AI needs to call tools
    while turn_count < max_turns:
        turn_count += 1
        
        payload = {
            "contents": history_for_api,
            "tools": [{
                "function_declarations": GEMINI_TOOLS
            }],
            "tool_config": {
                "function_calling_config": {
                    "mode": "AUTO"  # AUTO mode doesn't support allowed_function_names
                }
            },
            "system_instruction": {"parts": [{"text": system_prompt_text}]}
        }

        try:
            result = await call_gemini_with_retry(payload, gemini_api_key=request.gemini_api_key)
            
            # Check for valid response structure
            if not result.get("candidates") or not result["candidates"]:
                print("AI Error: Invalid response structure", result)
                raise HTTPException(status_code=500, detail="AI service returned an invalid response.")

            candidate = result["candidates"][0]
            if not candidate.get("content") or not candidate["content"].get("parts"):
                print("AI Error: Missing content in response", result)
                raise HTTPException(status_code=500, detail="AI service returned incomplete response.")

            model_parts = candidate["content"]["parts"]

            # Separate function calls and text responses
            function_calls_in_turn = [part["functionCall"] for part in model_parts if "functionCall" in part]
            text_response_parts = [part for part in model_parts if "text" in part]

            if function_calls_in_turn:
                # The model wants to call function(s)
                print(f"Turn {turn_count}: Processing {len(function_calls_in_turn)} function call(s)")
                
                # Add the model's function call(s) to history
                history_for_api.append({
                    "role": "model", 
                    "parts": [{"functionCall": fc} for fc in function_calls_in_turn]
                })

                # Execute all function calls and collect responses
                function_responses = []
                for function_call in function_calls_in_turn:
                    tool_name = function_call["name"]
                    tool_args = function_call.get("args", {})

                    print(f"AI calling tool: {tool_name} with args: {tool_args}")

                    if tool_name in AVAILABLE_TOOLS:
                        tool_function = AVAILABLE_TOOLS[tool_name]
                        
                        try:
                            # Execute the tool function
                            tool_result_json = tool_function(db=db, **tool_args)
                            parsed_tool_response = json.loads(tool_result_json)

                            # Based on official Gemini API schema, functionResponse needs name and response fields
                            function_responses.append({
                                "functionResponse": {
                                    "name": tool_name,
                                    "response": parsed_tool_response
                                }
                            })
                        except Exception as tool_error:
                            print(f"Tool execution error for {tool_name}: {tool_error}")
                            function_responses.append({
                                "functionResponse": {
                                    "name": tool_name,
                                    "response": {"error": f"Tool execution failed: {str(tool_error)}"}
                                }
                            })
                    else:
                        print(f"AI requested unknown tool: {tool_name}")
                        function_responses.append({
                            "functionResponse": {
                                "name": tool_name,
                                "response": {"error": f"Unknown tool: {tool_name}"}
                            }
                        })
                
                # Add all function responses as a single "user" turn (as per Gemini documentation)
                history_for_api.append({
                    "role": "user", 
                    "parts": function_responses
                })
                
                # Continue to get the model's final response
                continue
                
            elif text_response_parts:
                # The model has generated a final text answer
                final_answer = text_response_parts[0]["text"]
                print(f"AI analysis completed in {turn_count} turns")
                return {"text": final_answer}
                
            else:
                # Unexpected response format
                print("AI Error: Response was neither text nor function call.", model_parts)
                raise HTTPException(status_code=500, detail="AI service returned an unexpected response format.")

        except HTTPException:
            # Re-raise HTTP exceptions (already properly formatted)
            raise
        except Exception as e:
            print(f"Unexpected error in turn {turn_count}: {e}")
            raise HTTPException(status_code=500, detail="An internal server error occurred during AI analysis.")


    # If we've exceeded max turns, return an error
    raise HTTPException(status_code=500, detail="AI analysis exceeded maximum conversation turns. Please try again.")

# --- Flashcard Endpoints ---
@app.post("/api/flashcards/save", response_model=FlashcardSetResponse, status_code=201)
async def save_flashcard_set(flashcard_set: FlashcardSetCreate, db: Session = Depends(get_db)):
    """Save a new flashcard set"""
    try:
        # Convert flashcards to JSON string
        flashcards_json = json.dumps([card.dict() for card in flashcard_set.flashcards])
        
        # Create new flashcard set
        db_flashcard_set = FlashcardSetDB(
            name=flashcard_set.name,
            topics=flashcard_set.topics,
            flashcards_json=flashcards_json,
            created_at=datetime.datetime.utcnow()
        )
        
        db.add(db_flashcard_set)
        db.commit()
        db.refresh(db_flashcard_set)
        
        # Convert back to response format
        flashcards_data = json.loads(db_flashcard_set.flashcards_json)
        flashcards = [Flashcard(**card) for card in flashcards_data]
        
        return FlashcardSetResponse(
            id=db_flashcard_set.id,
            name=db_flashcard_set.name,
            topics=db_flashcard_set.topics,
            flashcards=flashcards,
            created_at=db_flashcard_set.created_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save flashcard set: {str(e)}")

@app.get("/api/flashcards/list", response_model=List[FlashcardSetResponse])
async def list_flashcard_sets(db: Session = Depends(get_db)):
    """Get all saved flashcard sets"""
    try:
        flashcard_sets = db.query(FlashcardSetDB).order_by(FlashcardSetDB.created_at.desc()).all()
        
        result = []
        for db_set in flashcard_sets:
            try:
                flashcards_data = json.loads(db_set.flashcards_json)
                flashcards = [Flashcard(**card) for card in flashcards_data]
                
                result.append(FlashcardSetResponse(
                    id=db_set.id,
                    name=db_set.name,
                    topics=db_set.topics,
                    flashcards=flashcards,
                    created_at=db_set.created_at
                ))
            except json.JSONDecodeError:
                # Skip corrupted flashcard sets
                continue
                
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load flashcard sets: {str(e)}")

@app.get("/api/flashcards/{flashcard_set_id}", response_model=FlashcardSetResponse)
async def get_flashcard_set(flashcard_set_id: int, db: Session = Depends(get_db)):
    """Get a specific flashcard set by ID"""
    try:
        db_set = db.query(FlashcardSetDB).filter(FlashcardSetDB.id == flashcard_set_id).first()
        
        if not db_set:
            raise HTTPException(status_code=404, detail="Flashcard set not found")
        
        flashcards_data = json.loads(db_set.flashcards_json)
        flashcards = [Flashcard(**card) for card in flashcards_data]

        return FlashcardSetResponse(
            id=db_set.id,
            name=db_set.name,
            topics=db_set.topics,
            flashcards=flashcards,
            created_at=db_set.created_at
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupted flashcard set data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load flashcard set: {str(e)}")

@app.delete("/api/flashcards/delete/{flashcard_set_id}")
async def delete_flashcard_set(flashcard_set_id: int, db: Session = Depends(get_db)):
    """Delete a flashcard set"""
    try:
        db_set = db.query(FlashcardSetDB).filter(FlashcardSetDB.id == flashcard_set_id).first()
        
        if not db_set:
            raise HTTPException(status_code=404, detail="Flashcard set not found")
        
        db.delete(db_set)
        db.commit()
        
        return {"message": "Flashcard set deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete flashcard set: {str(e)}")

# --- Individual Flashcard Endpoints ---
@app.post("/api/flashcards/save-individual", response_model=IndividualFlashcardResponse, status_code=201)
async def save_individual_flashcard(flashcard: IndividualFlashcardCreate, db: Session = Depends(get_db)):
    """Save a single individual flashcard"""
    try:
        # Convert flashcard to JSON string
        flashcard_json = json.dumps(flashcard.flashcard.dict())
        
        # Create new individual flashcard
        db_flashcard = IndividualFlashcardDB(
            name=flashcard.name,
            topics=flashcard.topics,
            flashcard_json=flashcard_json,
            created_at=datetime.datetime.utcnow()
        )
        
        db.add(db_flashcard)
        db.commit()
        db.refresh(db_flashcard)
        
        # Convert back to response format
        flashcard_data = json.loads(db_flashcard.flashcard_json)
        flashcard_obj = Flashcard(**flashcard_data)
        
        return IndividualFlashcardResponse(
            id=db_flashcard.id,
            name=db_flashcard.name,
            topics=db_flashcard.topics,
            flashcard=flashcard_obj,
            created_at=db_flashcard.created_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save individual flashcard: {str(e)}")

@app.get("/api/flashcards/individual/{flashcard_id}", response_model=IndividualFlashcardResponse)
async def get_individual_flashcard(flashcard_id: int, db: Session = Depends(get_db)):
    """Get a specific individual flashcard by ID"""
    try:
        db_card = db.query(IndividualFlashcardDB).filter(IndividualFlashcardDB.id == flashcard_id).first()
        
        if not db_card:
            raise HTTPException(status_code=404, detail="Individual flashcard not found")
        
        flashcard_data = json.loads(db_card.flashcard_json)
        flashcard_obj = Flashcard(**flashcard_data)
        
        return IndividualFlashcardResponse(
            id=db_card.id,
            name=db_card.name,
            topics=db_card.topics,
            flashcard=flashcard_obj,
            created_at=db_card.created_at
        )
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupted individual flashcard data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load individual flashcard: {str(e)}")

@app.delete("/api/flashcards/delete-individual/{flashcard_id}")
async def delete_individual_flashcard(flashcard_id: int, db: Session = Depends(get_db)):
    """Delete an individual flashcard"""
    try:
        db_card = db.query(IndividualFlashcardDB).filter(IndividualFlashcardDB.id == flashcard_id).first()
        
        if not db_card:
            raise HTTPException(status_code=404, detail="Individual flashcard not found")
        
        db.delete(db_card)
        db.commit()
        
        return {"message": "Individual flashcard deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete individual flashcard: {str(e)}")

