# --- This code should be CUT from main.py and PASTED into models.py ---

import datetime
import secrets
import os
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# It's important to move Base here as well
Base = declarative_base()

# --- Database Models (SQLAlchemy ORM) ---

class QuizDB(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    time_limit_minutes = Column(Integer, nullable=False, default=10)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    questions = relationship("QuestionDB", back_populates="quiz", cascade="all, delete-orphan")
    performance_records = relationship("PerformanceDB", back_populates="quiz", cascade="all, delete-orphan")
    created_by = relationship("UserDB", back_populates="quizzes")

    def __repr__(self):
        return f"<Quiz(id={self.id}, name='{self.name}', time_limit={self.time_limit_minutes}min)>"

class RCPassageDB(Base):
    __tablename__ = "rc_passages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    passage_text = Column(Text, nullable=False)

    questions = relationship("QuestionDB", back_populates="rc_passage")

    def __repr__(self):
        return f"<RCPassage(id={self.id}, title='{self.title or 'No Title'}', text='{self.passage_text[:50]}...')>"

class QuestionDB(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    rc_id = Column(Integer, ForeignKey("rc_passages.id"), nullable=True)
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=False)
    correct_answer = Column(String, nullable=False)
    answer_explanation = Column(Text, nullable=True)
    image = Column(String, nullable=True)
    difficulty = Column(String, nullable=False, default="medium")
    question_type = Column(String, nullable=False)
    subsection = Column(String, nullable=True)

    quiz = relationship("QuizDB", back_populates="questions")
    rc_passage = relationship("RCPassageDB", back_populates="questions")

    def __repr__(self):
        return f"<Question(id={self.id}, quiz_id={self.quiz_id}, type='{self.question_type}', sub='{self.subsection}', rc_id={self.rc_id}, text='{self.question_text[:30]}...')>"

class PerformanceDB(Base):
    __tablename__ = "performance"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    time_taken_seconds = Column(Integer, nullable=False)
    quiz = relationship("QuizDB", back_populates="performance_records")
    user_explanations = relationship("UserExplanationDB", back_populates="performance", cascade="all, delete-orphan")
    detailed_results = relationship("DetailedResultDB", back_populates="performance", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Performance(id={self.id}, quiz_id={self.quiz_id}, score={self.correct_answers}/{self.total_questions}, time={self.time_taken_seconds}s)>"

class UserExplanationDB(Base):
    __tablename__ = "user_explanations"

    id = Column(Integer, primary_key=True, index=True)
    performance_id = Column(Integer, ForeignKey("performance.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    explanation_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    performance = relationship("PerformanceDB", back_populates="user_explanations")
    question = relationship("QuestionDB")

    def __repr__(self):
        return f"<UserExplanation(id={self.id}, performance_id={self.performance_id}, question_id={self.question_id})>"


class DetailedResultDB(Base):
    __tablename__ = "detailed_results"

    id = Column(Integer, primary_key=True, index=True)
    performance_id = Column(Integer, ForeignKey("performance.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    correct = Column(Boolean, nullable=False)
    user_answer = Column(String, nullable=True)
    time_spent = Column(Integer, nullable=True)

    performance = relationship("PerformanceDB", back_populates="detailed_results")
    question = relationship("QuestionDB")

class FlashcardSetDB(Base):
    __tablename__ = "flashcard_sets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    topics = Column(String, nullable=True)
    flashcards_json = Column(Text, nullable=False)  # Store flashcards as JSON
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<FlashcardSet(id={self.id}, name='{self.name}', created_at='{self.created_at}')>"

class IndividualFlashcardDB(Base):
    __tablename__ = "individual_flashcards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    topics = Column(String, nullable=True)
    flashcard_json = Column(Text, nullable=False)  # Store single flashcard as JSON
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<IndividualFlashcard(id={self.id}, name='{self.name}', created_at='{self.created_at}')>"

# --- Authentication Models ---
class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # Changed from hashed_password
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    database_path = Column(String, nullable=True) # Path to the user's sqlite DB

    api_keys = relationship("APIKeyDB", back_populates="user", cascade="all, delete-orphan")
    quizzes = relationship("QuizDB", back_populates="created_by")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}', active={self.is_active})>"
    
    @staticmethod
    def get_user_db_path(user_id):
        """Get the database path for a specific user"""
        user_db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_databases')
        os.makedirs(user_db_dir, exist_ok=True)
        return os.path.join(user_db_dir, f"{user_id}.db")
    
    @staticmethod
    def create_user_db(user_id):
        """Create a new database for the user with all tables"""
        db_path = UserDB.get_user_db_path(user_id)
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        
        # Create all tables except authentication-related ones
        tables_to_create = [
            QuizDB.__table__, 
            QuestionDB.__table__, 
            PerformanceDB.__table__,
            UserExplanationDB.__table__,
            FlashcardSetDB.__table__,
            IndividualFlashcardDB.__table__,
            RCPassageDB.__table__
        ]
        
        # Create the tables in the user's database
        for table in tables_to_create:
            if not table.name in ["users", "api_keys"]:  # Skip auth tables
                table.create(engine, checkfirst=True)
                
        return db_path
    
    @staticmethod
    def get_user_db_engine(user_id):
        """Get a database engine for the user's database"""
        db_path = UserDB.get_user_db_path(user_id)
        if not os.path.exists(db_path):
            UserDB.create_user_db(user_id)
        return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    @staticmethod
    def get_user_db_session(user_id):
        """Get a database session for the user's database"""
        engine = UserDB.get_user_db_engine(user_id)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal()

class APIKeyDB(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration

    user = relationship("UserDB", back_populates="api_keys")

    def __repr__(self):
        return f"<APIKey(id={self.id}, user_id={self.user_id}, name='{self.key_name}', active={self.is_active})>"

    @staticmethod
    def generate_api_key():
        """Generate a secure API key"""
        return f"gmat_quiz_{secrets.token_urlsafe(32)}"