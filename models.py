# --- This code should be CUT from main.py and PASTED into models.py ---

import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

# It's important to move Base here as well
Base = declarative_base()

# --- Database Models (SQLAlchemy ORM) ---

class QuizDB(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    time_limit_minutes = Column(Integer, nullable=False, default=10)

    questions = relationship("QuestionDB", back_populates="quiz", cascade="all, delete-orphan")
    performance_records = relationship("PerformanceDB", back_populates="quiz", cascade="all, delete-orphan")

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
    detailed_results_json = Column(Text, nullable=True)

    quiz = relationship("QuizDB", back_populates="performance_records")
    user_explanations = relationship("UserExplanationDB", back_populates="performance", cascade="all, delete-orphan")

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