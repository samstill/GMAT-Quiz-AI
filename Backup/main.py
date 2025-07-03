# main.py - Your FastAPI Backend with Multiple Quizzes, Detailed Performance Tracking, and Time Limit

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, Session # Import joinedload for eager loading
from sqlalchemy.exc import IntegrityError, OperationalError
import json
import os
import shutil
import datetime # To record submission time

# --- Database Configuration ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./quiz.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Database Models (SQLAlchemy ORM) ---

class QuizDB(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False) # Custom name for the quiz
    time_limit_minutes = Column(Integer, nullable=False, default=10) # New field for time limit in minutes

    # Relationships
    questions = relationship("QuestionDB", back_populates="quiz", cascade="all, delete-orphan") # Add cascade delete
    performance_records = relationship("PerformanceDB", back_populates="quiz", cascade="all, delete-orphan") # Add cascade delete

    def __repr__(self):
        return f"<Quiz(id={self.id}, name='{self.name}', time_limit={self.time_limit_minutes}min)>"

# Add new model for RC Passages
class RCPassageDB(Base):
    __tablename__ = "rc_passages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True) # Optional title for the passage
    passage_text = Column(Text, nullable=False)

    # Relationship back to questions (optional, for convenience)
    questions = relationship("QuestionDB", back_populates="rc_passage")

    def __repr__(self):
        return f"<RCPassage(id={self.id}, title='{self.title or 'No Title'}', text='{self.passage_text[:50]}...')>"


class QuestionDB(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False) # Link to Quiz
    rc_id = Column(Integer, ForeignKey("rc_passages.id"), nullable=True) # New field: Link to RC Passage (optional)
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=False)
    correct_answer = Column(String, nullable=False)
    answer_explanation = Column(Text, nullable=True) # New field: Explanation for the correct answer
    image = Column(String, nullable=True) # Filename of the image
    difficulty = Column(String, nullable=False, default="medium")
    question_type = Column(String, nullable=False) # New field: 'Quant', 'Verbal', 'Data Insights'
    subsection = Column(String, nullable=True) # New field: 'RC', 'CR' (for Verbal)

    # Relationships
    quiz = relationship("QuizDB", back_populates="questions")
    rc_passage = relationship("RCPassageDB", back_populates="questions") # Relationship to RC Passage

    def __repr__(self):
        return f"<Question(id={self.id}, quiz_id={self.quiz_id}, type='{self.question_type}', sub='{self.subsection}', rc_id={self.rc_id}, text='{self.question_text[:30]}...')>"

class PerformanceDB(Base):
    __tablename__ = "performance"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False) # Link to Quiz
    timestamp = Column(DateTime, default=datetime.datetime.utcnow) # When the quiz was submitted
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    time_taken_seconds = Column(Integer, nullable=False) # Time taken in seconds
    # New field to store detailed results per question
    detailed_results_json = Column(Text, nullable=True) # Store list of {question_id, correct, difficulty} # Difficulty field might be redundant if we store type/subsection

    # Relationships
    quiz = relationship("QuizDB", back_populates="performance_records")
    user_explanations = relationship("UserExplanationDB", back_populates="performance", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Performance(id={self.id}, quiz_id={self.quiz_id}, score={self.correct_answers}/{self.total_questions}, time={self.time_taken_seconds}s)>"

# New model for storing user explanations for incorrect questions
class UserExplanationDB(Base):
    __tablename__ = "user_explanations"

    id = Column(Integer, primary_key=True, index=True)
    performance_id = Column(Integer, ForeignKey("performance.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    explanation_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    performance = relationship("PerformanceDB", back_populates="user_explanations")
    question = relationship("QuestionDB")

    def __repr__(self):
        return f"<UserExplanation(id={self.id}, performance_id={self.performance_id}, question_id={self.question_id})>"


# Create database tables (includes the new quiz table and updated foreign keys)
# NOTE: If quiz.db already exists from a previous version, you will need to
# delete it and restart the server to apply the new schema.
Base.metadata.create_all(bind=engine) # Create new table/columns

# Migration function to add answer_explanation column if it doesn't exist
def migrate_database():
    """
    Adds the answer_explanation column to the questions table if it doesn't exist.
    This is needed for existing databases that don't have this column.
    """
    db = SessionLocal()
    try:
        # Try to query the answer_explanation column to see if it exists
        db.execute(text("SELECT answer_explanation FROM questions LIMIT 1"))
        print("Database migration: answer_explanation column already exists")
    except OperationalError as e:
        # Column doesn't exist (OperationalError: no such column), add it
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

# Run migration
migrate_database()


# --- Pydantic Models (for Request/Response Validation) ---

class QuizBase(BaseModel):
    name: str
    time_limit_minutes: int # Include time limit

class QuizCreate(QuizBase):
    pass

class QuizResponse(QuizBase):
    id: int

    class Config:
        from_attributes = True

# New Pydantic models for RC Passage
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
    answerExplanation: Optional[str] = None # New field: Explanation for the correct answer
    image: Optional[str] = None
    difficulty: str # Keep difficulty for now, but question_type/subsection are more specific
    rc_id: Optional[int] = None # Link to RC Passage (optional)
    question_type: str # New field: 'Quant', 'Verbal', 'Data Insights'
    subsection: Optional[str] = None # New field: 'RC', 'CR' (for Verbal)

class QuestionCreate(QuestionBase):
    pass # Use QuestionBase for creation

# Updated QuestionResponse to include rc_id, rc_passage, type, and subsection
class QuestionResponse(BaseModel): # Used for question retrieval responses
    id: int
    quiz_id: int # Include quiz_id in the response
    rc_id: Optional[int] = None # Include rc_id
    # Include the full RC passage object if linked
    rc_passage: Optional[RCPassageResponse] = None
    questionText: str
    options: List[str]
    correctAnswer: str
    answerExplanation: Optional[str] = None # Include answer explanation
    image: Optional[str] = None
    difficulty: str
    question_type: str # Include question_type
    subsection: Optional[str] = None # Include subsection


    class Config:
        from_attributes = True


# Model for detailed result of a single question
class DetailedQuestionResult(BaseModel):
    questionId: int
    correct: bool
    difficulty: str # Keep difficulty for now, but could replace with type/subsection
    userAnswer: Optional[str] = None # The answer the user selected
    correctAnswer: str # The correct answer
    questionText: str # The full question text
    options: List[str] # All available options
    question_type: str # Question type: 'Quant', 'Verbal', 'Data Insights'
    subsection: Optional[str] = None # Subsection like 'RC', 'CR' for Verbal
    timeSpent: Optional[int] = None # Time spent on this question in seconds
    answerExplanation: Optional[str] = None # Official explanation for the correct answer

# Enhanced model for performance review with complete question details
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
    answerExplanation: Optional[str] = None # Official explanation for the correct answer
    # Additional fields for RC questions
    rc_passage: Optional[RCPassageResponse] = None
    # User explanation for this question (if exists)
    userExplanation: Optional[str] = None

# Pydantic models for user explanations
class UserExplanationBase(BaseModel):
    explanation_text: str

class UserExplanationCreate(UserExplanationBase):
    question_id: int

    class Config:
        populate_by_name = True
        # This allows both snake_case from JSON and camelCase

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

class PerformanceCreate(BaseModel): # Used for receiving performance data from frontend
    quizId: int # Include quiz ID
    totalQuestions: int
    correctAnswers: int
    timeTakenSeconds: int
    detailedResults: List[DetailedQuestionResult] # New field for detailed results

class PerformanceResponse(BaseModel): # Used for sending performance data to frontend
    id: int
    quizId: int # Include quiz ID
    timestamp: datetime.datetime
    totalQuestions: int
    correctAnswers: int
    timeTakenSeconds: int
    detailedResults: List[DetailedQuestionResult] # Include detailed results in response

    class Config:
        from_attributes = True # Allows Pydantic to read from SQLAlchemy model attributes

class BulkQuestionCreate(BaseModel):
    questionText: str
    options: List[str]
    correctAnswer: str
    answerExplanation: Optional[str] = None # Include answer explanation in bulk create
    difficulty: str
    rc_id: Optional[int] = None # Include rc_id in bulk create
    question_type: str # Include question_type in bulk create
    subsection: Optional[str] = None # Include subsection in bulk create


# --- FastAPI Application Setup ---
app = FastAPI()

# Configure CORS
# This allows requests from any origin, which is important for frontend running on a different address/port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# Serve static files (images) from the 'images' directory
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True) # Create the directory if it doesn't exist
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Quiz API!"}

# --- Quiz Management Endpoints ---

@app.post("/api/quizzes/", response_model=QuizResponse, status_code=201)
async def create_quiz(quiz: QuizCreate, db: Session = Depends(get_db)):
    """
    Creates a new quiz with a custom name and time limit.
    """
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
    """
    Retrieves a list of all quizzes.
    """
    quizzes_db = db.query(QuizDB).all()
    return quizzes_db

@app.get("/api/quizzes/{quiz_id}", response_model=QuizResponse)
async def read_quiz(quiz_id: int = Path(..., title="The ID of the quiz to get"), db: Session = Depends(get_db)):
    """
    Retrieves details for a specific quiz.
    """
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return db_quiz

# --- RC Passage Management Endpoints ---
@app.post("/api/rc_passages/", response_model=RCPassageResponse, status_code=201)
async def create_rc_passage(rc_passage: RCPassageCreate, db: Session = Depends(get_db)):
    """
    Creates a new RC passage.
    """
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
    """
    Retrieves a list of all RC passages.
    """
    rc_passages_db = db.query(RCPassageDB).all()
    return rc_passages_db

@app.get("/api/rc_passages/{rc_id}", response_model=RCPassageResponse)
async def read_rc_passage(rc_id: int = Path(..., title="The ID of the RC passage to get"), db: Session = Depends(get_db)):
    """
    Retrieves details for a specific RC passage.
    """
    db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
    if db_rc_passage is None:
        raise HTTPException(status_code=404, detail="RC Passage not found")
    return db_rc_passage

@app.put("/api/rc_passages/{rc_id}", response_model=RCPassageResponse)
async def update_rc_passage(rc_id: int, rc_passage: RCPassageCreate, db: Session = Depends(get_db)):
    """
    Updates an existing RC passage.
    """
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
    """
    Deletes an RC passage and unlinks any associated questions.
    """
    db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
    if db_rc_passage is None:
        raise HTTPException(status_code=404, detail="RC Passage not found")

    # Unlink questions associated with this passage
    questions_to_unlink = db.query(QuestionDB).filter(QuestionDB.rc_id == rc_id).all()
    for question in questions_to_unlink:
        question.rc_id = None # Set rc_id to NULL

    db.delete(db_rc_passage)
    db.commit()
    return # No content (204) for successful deletion


# --- Question Management Endpoints (Linked to Quizzes) ---

# Endpoint to get a single question by ID (needed for edit logic in frontend)
@app.get("/api/questions/{question_id}", response_model=QuestionResponse)
async def read_question(question_id: int = Path(..., title="The ID of the question to get"), db: Session = Depends(get_db)):
    """
    Retrieves a single question by its ID, including associated RC passage details if any.
    """
    # Fetch the question and eagerly load the associated RC passage
    db_question = db.query(QuestionDB).options(
        joinedload(QuestionDB.rc_passage) # Eager load the relationship
    ).filter(QuestionDB.id == question_id).first()

    if db_question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    rc_passage_response = None
    if db_question.rc_passage:
        # Use model_validate to convert RCPassageDB object to RCPassageResponse Pydantic model
        rc_passage_response = RCPassageResponse.model_validate(db_question.rc_passage)    
    return QuestionResponse(
        id=db_question.id,
        quiz_id=db_question.quiz_id,
        rc_id=db_question.rc_id,
        rc_passage=rc_passage_response, # Include the RCPassageResponse object
        questionText=db_question.question_text,
        options=json.loads(db_question.options_json),
        correctAnswer=db_question.correct_answer,
        answerExplanation=db_question.answer_explanation, # Include answer explanation
        image=db_question.image,
        difficulty=db_question.difficulty,
        question_type=db_question.question_type, # Include question type
        subsection=db_question.subsection # Include subsection
    )


# Endpoint to add a new question to a specific quiz (handles file upload)
@app.post("/api/quizzes/{quiz_id}/questions/", response_model=QuestionResponse, status_code=201)
async def create_question_for_quiz(
    quiz_id: int = Path(..., title="The ID of the quiz to add the question to"),
    question: str = Form(...), # Receive question data as JSON string in a form field
    image_file: Optional[UploadFile] = File(None), # Receive optional image file
    db: Session = Depends(get_db)
):
    """
    Adds a new question with type, subsection, optional image, and optional RC passage link to a specific quiz.
    """
    # Verify the quiz exists
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

    try:
        question_data = json.loads(question)
        question_text = question_data.get("questionText")
        options = question_data.get("options")
        correct_answer = question_data.get("correctAnswer")
        answer_explanation = question_data.get("answerExplanation") # Get answer explanation
        difficulty = question_data.get("difficulty")
        rc_id = question_data.get("rc_id") # Get optional rc_id
        question_type = question_data.get("question_type") # Get question type
        subsection = question_data.get("subsection") # Get subsection
        image_filename_from_data = question_data.get("image") # Filename if no file uploaded

        if not all([question_text, options, correct_answer, difficulty, question_type]):
             raise HTTPException(status_code=400, detail="Missing required question data (text, options, answer, difficulty, type).")

        # Basic validation for question_type and subsection consistency
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
        # For Quant and Data Insights, rc_id should also be None
        if question_type in ["Quant", "Data Insights"] and rc_id is not None:
             raise HTTPException(status_code=400, detail=f"RC Passage link must be null for question_type {question_type}.")


        # Verify RC passage exists if rc_id is provided
        if rc_id is not None:
            db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
            if db_rc_passage is None:
                raise HTTPException(status_code=404, detail=f"RC Passage with ID {rc_id} not found.")


        image_filename = None
        if image_file:
            # Save the uploaded file
            file_location = os.path.join(IMAGES_DIR, image_file.filename)
            # Ensure filename uniqueness if necessary in a real app
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(image_file.file, buffer)
            image_filename = image_file.filename
        elif image_filename_from_data: # This part might not be needed if frontend always sends file on update
             # If no file uploaded but filename provided, use it (assuming it exists)
             image_filename = image_filename_from_data


        db_question = QuestionDB(

            quiz_id=quiz_id, # Link the question to the quiz
            rc_id=rc_id, # Save the optional rc_id
            question_text=question_text,
            options_json=json.dumps(options),
            correct_answer=correct_answer,
            answer_explanation=answer_explanation, # Save answer explanation
            image=image_filename,
            difficulty=difficulty,
            question_type=question_type, # Save question type
            subsection=subsection # Save subsection
        )
        db.add(db_question)
        try:
            db.commit()
            db.refresh(db_question)
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Question could not be added due to a database error.")

        # Fetch the associated RC passage for the response if rc_id exists
        rc_passage_response = None
        if db_question.rc_id:
             db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == db_question.rc_id).first()
             if db_rc_passage:
                  rc_passage_response = RCPassageResponse.model_validate(db_rc_passage)


        return QuestionResponse(
            id=db_question.id,
            quiz_id=db_question.quiz_id,
            rc_id=db_question.rc_id,
            rc_passage=rc_passage_response, # Include the RC passage object
            questionText=db_question.question_text,
            options=json.loads(db_question.options_json),
            correctAnswer=db_question.correct_answer,
            answerExplanation=db_question.answer_explanation, # Include answer explanation
            image=db_question.image,
            difficulty=db_question.difficulty,
            question_type=db_question.question_type, # Include question type
            subsection=db_question.subsection # Include subsection
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for question data.")
    except Exception as e:
        print(f"An error occurred during question creation: {e}")
        # Check if the error is due to missing required fields based on type/subtype
        if "Missing required question data" in str(e) or "Invalid" in str(e):
             raise
        raise HTTPException(status_code=500, detail="An internal server error occurred.")


# Endpoint to retrieve questions for a specific quiz (now includes RC passage, type, subsection)
@app.get("/api/quizzes/{quiz_id}/questions/", response_model=List[QuestionResponse])
async def read_questions_for_quiz(quiz_id: int = Path(..., title="The ID of the quiz to get questions for"), db: Session = Depends(get_db)):
    """
    Retrieves all questions for a specific quiz, including associated RC passage details, type, and subsection if any.
    """
     # Verify the quiz exists
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Fetch questions and eagerly load the associated RC passage
    questions_db = db.query(QuestionDB).options(
        joinedload(QuestionDB.rc_passage) # Eager load the relationship
    ).filter(QuestionDB.quiz_id == quiz_id).all()    # Manually construct QuestionResponse objects to include RC passage data
    response_list = []
    for q in questions_db:
        rc_passage_response = None
        if q.rc_passage:
            print(f"Backend: Found RC passage {q.rc_passage.id} for question {q.id}. Text length: {len(q.rc_passage.passage_text) if q.rc_passage.passage_text else 0}")
            print(f"Backend: RC Passage object details: ID={q.rc_passage.id}, Title='{q.rc_passage.title}', Text='{q.rc_passage.passage_text[:50]}...')")
            # Use model_validate to convert RCPassageDB object to RCPassageResponse Pydantic model
            rc_passage_response = RCPassageResponse.model_validate(q.rc_passage)
        
        response_list.append(QuestionResponse(
            id=q.id,
            quiz_id=q.quiz_id,
            rc_id=q.rc_id,
            rc_passage=rc_passage_response, # Include the RCPassageResponse object
            questionText=q.question_text,
            options=json.loads(q.options_json),
            correctAnswer=q.correct_answer,
            image=q.image,
            difficulty=q.difficulty,
            question_type=q.question_type, # Include question type
            subsection=q.subsection, # Include subsection
            answerExplanation=q.answer_explanation # Include answer explanation
        ))

    return response_list


# Endpoint to delete a question (still by question ID)
@app.delete("/api/questions/{question_id}", status_code=204)
async def delete_question(question_id: int, db: Session = Depends(get_db)):
    """
    Deletes a question by its ID and its associated image file.
    """
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
    return # No content (204) for successful deletion

# Endpoint to update a question (by question ID)
@app.put("/api/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: int,
    question: str = Form(...),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Updates an existing question, including its text, options, correct answer, difficulty, optional image, optional RC passage link, type, and subsection.
    """
    db_question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
    if db_question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        question_data = json.loads(question)
        question_text = question_data.get("questionText")
        options = question_data.get("options")
        correct_answer = question_data.get("correctAnswer")
        answer_explanation = question_data.get("answerExplanation") # Get answer explanation
        difficulty = question_data.get("difficulty")
        rc_id = question_data.get("rc_id") # Get optional rc_id
        question_type = question_data.get("question_type") # Get question type
        subsection = question_data.get("subsection") # Get subsection

        if not all([question_text, options, correct_answer, difficulty, question_type]):
            raise HTTPException(status_code=400, detail="Missing required question data (text, options, answer, difficulty, type).")

        # Basic validation for question_type and subsection consistency
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
        # For Quant and Data Insights, rc_id should also be None
        if question_type in ["Quant", "Data Insights"] and rc_id is not None:
             raise HTTPException(status_code=400, detail=f"RC Passage link must be null for question_type {question_type}.")


        # Verify RC passage exists if rc_id is provided
        if rc_id is not None:
             db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
             if db_rc_passage is None:
                 raise HTTPException(status_code=404, detail=f"RC Passage with ID {rc_id} not found.")
        # If rc_id is None, the question will be unlinked from any passage


        # Handle image update
        if image_file:
            # Delete old image if exists
            if db_question.image:
                old_image_path = os.path.join(IMAGES_DIR, db_question.image)
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except OSError:
                        pass
            # Save new image
            file_location = os.path.join(IMAGES_DIR, image_file.filename)
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(image_file.file, buffer)
            db_question.image = image_file.filename
        # If no new image uploaded, keep the old image
        
        db_question.question_text = question_text
        db_question.options_json = json.dumps(options)
        db_question.correct_answer = correct_answer
        db_question.answer_explanation = answer_explanation # Update answer explanation
        db_question.difficulty = difficulty
        db_question.rc_id = rc_id # Update rc_id
        db_question.question_type = question_type # Update question type
        db_question.subsection = subsection # Update subsection

        db.commit()
        db.refresh(db_question)

        # Fetch the associated RC passage for the response if rc_id exists
        rc_passage_response = None
        if db_question.rc_id:
             db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == db_question.rc_id).first()
             if db_rc_passage:
                  rc_passage_response = RCPassageResponse.model_validate(db_rc_passage)

        return QuestionResponse(
            id=db_question.id,
            quiz_id=db_question.quiz_id,
            rc_id=db_question.rc_id,
            rc_passage=rc_passage_response, # Include the RC passage object
            questionText=db_question.question_text,
            options=json.loads(db_question.options_json),
            correctAnswer=db_question.correct_answer,
            answerExplanation=db_question.answer_explanation, # Include answer explanation
            image=db_question.image,
            difficulty=db_question.difficulty,
            question_type=db_question.question_type, # Include question type
            subsection=db_question.subsection # Include subsection
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for question data.")
    except Exception as e:
        print(f"An error occurred during question update: {e}")
        # Check if the error is due to missing required fields based on type/subtype
        if "Missing required question data" in str(e) or "Invalid" in str(e):
             raise
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

# Endpoint to delete a quiz and its associated questions and performance records
@app.delete("/api/quizzes/{quiz_id}", status_code=204)
async def delete_quiz(quiz_id: int = Path(..., title="The ID of the quiz to delete"), db: Session = Depends(get_db)):
    """
    Deletes a quiz and all its associated questions and performance records.
    Also deletes RC passages that are exclusively used by this quiz.
    """
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Collect all unique RC passage IDs associated with questions in this quiz
    rc_passage_ids = set()
    for question in db_quiz.questions:
        if question.rc_id is not None:
            rc_passage_ids.add(question.rc_id)
    
    # Identify RC passages that are exclusively used by this quiz's questions
    exclusive_rc_passage_ids = []
    for rc_id in rc_passage_ids:
        # Check if any questions from other quizzes use this RC passage
        other_quiz_questions = db.query(QuestionDB).filter(
            QuestionDB.rc_id == rc_id,
            QuestionDB.quiz_id != quiz_id
        ).first()
        
        # If no other quiz uses this RC passage, mark it for deletion
        if other_quiz_questions is None:
            exclusive_rc_passage_ids.append(rc_id)
    
    # Manually delete image files for questions in this quiz
    for question in db_quiz.questions:
         if question.image:
             image_path = os.path.join(IMAGES_DIR, question.image)
             if os.path.exists(image_path):
                 try:
                     os.remove(image_path)
                     print(f"Deleted image file: {image_path}")
                 except OSError as e:
                     print(f"Error deleting image file {image_path}: {e}")

    # Delete the quiz (this will cascade delete its questions and performance records)
    db.delete(db_quiz)
    db.commit()
    
    # Now delete RC passages that were exclusively used by this quiz
    for rc_id in exclusive_rc_passage_ids:
        db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
        if db_rc_passage:
            db.delete(db_rc_passage)
            print(f"Deleted RC passage {rc_id} that was exclusively used by quiz {quiz_id}")
    
    if exclusive_rc_passage_ids:
        db.commit()
        
    return # No content (204) for successful deletion


# --- Performance Endpoints (Linked to Quizzes) ---

@app.post("/api/performance/", status_code=201)
async def create_performance_record(performance_data: PerformanceCreate, db: Session = Depends(get_db)):
    """
    Saves a new quiz performance record with detailed results, linked to a quiz.
    Enhanced to store complete question information for detailed review.
    """
     # Verify the quiz exists
    db_quiz = db.query(QuizDB).filter(QuizDB.id == performance_data.quizId).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Enhance the detailed results with complete question information
    enhanced_results = []
    for result in performance_data.detailedResults:
        # Fetch the complete question data
        question = db.query(QuestionDB).options(
            joinedload(QuestionDB.rc_passage)
        ).filter(QuestionDB.id == result.questionId).first()
        
        if question:
            enhanced_result = {
                "questionId": result.questionId,
                "correct": result.correct,
                "difficulty": result.difficulty,
                "userAnswer": result.userAnswer,
                "correctAnswer": question.correct_answer,
                "questionText": question.question_text,
                "options": json.loads(question.options_json),                "question_type": question.question_type,
                "subsection": question.subsection,
                "timeSpent": result.timeSpent,
                "explanation": result.answerExplanation,
                # Include RC passage if applicable
                "rc_passage": {
                    "id": question.rc_passage.id,
                    "title": question.rc_passage.title,
                    "passage_text": question.rc_passage.passage_text
                } if question.rc_passage else None
            }
            enhanced_results.append(enhanced_result)

    db_performance = PerformanceDB(
        quiz_id=performance_data.quizId, # Link performance to the quiz
        total_questions=performance_data.totalQuestions,
        correct_answers=performance_data.correctAnswers,
        time_taken_seconds=performance_data.timeTakenSeconds,
        timestamp=datetime.datetime.utcnow(), # Record current time
        detailed_results_json=json.dumps(enhanced_results) if enhanced_results else None # Store enhanced detailed results as JSON string
    )
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
    """
    Retrieves quiz performance records, optionally filtered by quiz ID.
    """
    query = db.query(PerformanceDB)
    if quiz_id is not None:
         # Verify the quiz exists if filtering
        db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
        if db_quiz is None:
            raise HTTPException(status_code=404, detail="Quiz not found")
        query = query.filter(PerformanceDB.quiz_id == quiz_id)

    performance_records_db = query.order_by(PerformanceDB.timestamp).all() # Order by time

    return [
        PerformanceResponse(
            id=rec.id,
            quizId=rec.quiz_id, # Include quiz ID in response
            timestamp=rec.timestamp,
            totalQuestions=rec.total_questions,
            correctAnswers=rec.correct_answers,
            timeTakenSeconds=rec.time_taken_seconds,
            detailedResults=json.loads(rec.detailed_results_json) if rec.detailed_results_json else [] # Load JSON string back to list, handle None
        )
        for rec in performance_records_db
    ]

@app.get("/api/performance/{performance_id}", response_model=PerformanceResponse)
async def get_performance_record(
    performance_id: int = Path(..., title="The ID of the performance record to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a specific performance record by ID with basic detailed results.
    """
    performance_record = db.query(PerformanceDB).filter(PerformanceDB.id == performance_id).first()
    if performance_record is None:
        raise HTTPException(status_code=404, detail="Performance record not found")
    
    # Parse detailed results if available
    detailed_results = []
    if performance_record.detailed_results_json:
        try:
            parsed_results = json.loads(performance_record.detailed_results_json)
            # Convert to simplified DetailedQuestionResult format for basic response
            for result in parsed_results:
                simplified_result = DetailedQuestionResult(
                    questionId=result["questionId"],
                    correct=result["correct"],
                    difficulty=result["difficulty"],
                    userAnswer=result.get("userAnswer"),
                    correctAnswer=result["correctAnswer"],
                    questionText=result["questionText"],
                    options=result["options"],
                    question_type=result["question_type"],
                    subsection=result.get("subsection"),
                    timeSpent=result.get("timeSpent"),
                    answerExplanation=result.get("answerExplanation") # Use answerExplanation instead of explanation
                )
                detailed_results.append(simplified_result)
        except json.JSONDecodeError:
            detailed_results = []
    
    return PerformanceResponse(
        id=performance_record.id,
        quizId=performance_record.quiz_id,
        timestamp=performance_record.timestamp,
        totalQuestions=performance_record.total_questions,
        correctAnswers=performance_record.correct_answers,
        timeTakenSeconds=performance_record.time_taken_seconds,
        detailedResults=detailed_results
    )

@app.get("/api/performance/{performance_id}/detailed-review", response_model=List[DetailedPerformanceReview])
async def get_detailed_performance_review(
    performance_id: int = Path(..., title="The ID of the performance record to get detailed review for"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a detailed review of a specific quiz performance, including complete question information,
    user answers, correct answers, and explanations for comprehensive analysis.
    """
    # Fetch the performance record
    performance_record = db.query(PerformanceDB).filter(PerformanceDB.id == performance_id).first()
    if performance_record is None:
        raise HTTPException(status_code=404, detail="Performance record not found")
    
    # Parse the detailed results JSON
    if not performance_record.detailed_results_json:
        return []
    
    try:
        detailed_results = json.loads(performance_record.detailed_results_json)
        
        # Convert to DetailedPerformanceReview objects
        review_items = []
        for result in detailed_results:
            # Handle RC passage data if present
            rc_passage_data = None
            if result.get("rc_passage"):
                rc_passage_data = RCPassageResponse(
                    id=result["rc_passage"]["id"],
                    title=result["rc_passage"]["title"],
                    passage_text=result["rc_passage"]["passage_text"]
                )
              # Fetch user explanation for this question if it exists
            user_explanation = db.query(UserExplanationDB).filter(
                UserExplanationDB.performance_id == performance_id,
                UserExplanationDB.question_id == result["questionId"]
            ).first()
            
            review_item = DetailedPerformanceReview(
                questionId=result["questionId"],
                correct=result["correct"],
                userAnswer=result.get("userAnswer"),
                correctAnswer=result["correctAnswer"],
                questionText=result["questionText"],
                options=result["options"],
                difficulty=result["difficulty"],
                question_type=result["question_type"],
                subsection=result.get("subsection"),
                timeSpent=result.get("timeSpent"),
                answerExplanation=result.get("answerExplanation"), # Use answerExplanation instead of explanation
                rc_passage=rc_passage_data,
                userExplanation=user_explanation.explanation_text if user_explanation else None
            )
            review_items.append(review_item)
        
        return review_items
        
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing detailed results for performance {performance_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving detailed performance data")

@app.get("/api/performance/summary/{quiz_id}")
async def get_performance_summary(
    quiz_id: int = Path(..., title="The ID of the quiz to get performance summary for"),
    db: Session = Depends(get_db)
):
    """
    Get a comprehensive performance summary for a quiz including statistics by question type,
    difficulty level, and common mistakes.
    """
    # Verify the quiz exists
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Get all performance records for this quiz
    performance_records = db.query(PerformanceDB).filter(PerformanceDB.quiz_id == quiz_id).all()
    
    if not performance_records:
        return {
            "quizId": quiz_id,
            "quizName": db_quiz.name,
            "totalAttempts": 0,
            "summary": "No performance data available for this quiz."
        }
    
    # Aggregate statistics
    total_attempts = len(performance_records)
    total_questions_attempted = sum(record.total_questions for record in performance_records)
    total_correct_answers = sum(record.correct_answers for record in performance_records)
    average_score = (total_correct_answers / total_questions_attempted * 100) if total_questions_attempted > 0 else 0
    average_time = sum(record.time_taken_seconds for record in performance_records) / total_attempts
    
    # Analyze by question type and difficulty
    type_stats = {}
    difficulty_stats = {}
    common_mistakes = []
    
    for record in performance_records:
        if record.detailed_results_json:
            try:
                detailed_results = json.loads(record.detailed_results_json)
                for result in detailed_results:
                    q_type = result.get("question_type", "Unknown")
                    difficulty = result.get("difficulty", "Unknown")
                    correct = result.get("correct", False)
                    
                    # Track by question type
                    if q_type not in type_stats:
                        type_stats[q_type] = {"total": 0, "correct": 0}
                    type_stats[q_type]["total"] += 1
                    if correct:
                        type_stats[q_type]["correct"] += 1
                    
                    # Track by difficulty
                    if difficulty not in difficulty_stats:
                        difficulty_stats[difficulty] = {"total": 0, "correct": 0}
                    difficulty_stats[difficulty]["total"] += 1
                    if correct:
                        difficulty_stats[difficulty]["correct"] += 1
                    
                    # Track common mistakes (questions answered incorrectly)
                    if not correct:
                        mistake_entry = {
                            "questionId": result.get("questionId"),
                            "questionText": result.get("questionText", "")[:100] + "...",
                            "userAnswer": result.get("userAnswer"),
                            "correctAnswer": result.get("correctAnswer"),
                            "question_type": q_type,
                            "difficulty": difficulty
                        }
                        common_mistakes.append(mistake_entry)
            except json.JSONDecodeError:
                continue
    
    # Calculate percentages
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
        "commonMistakes": common_mistakes[:10],  # Show top 10 most common mistakes
        "recentPerformances": [
            {
                "id": record.id,
                "timestamp": record.timestamp.isoformat(),
                "score": f"{record.correct_answers}/{record.total_questions}",
                "percentage": round((record.correct_answers / record.total_questions * 100), 2),
                "timeMinutes": round(record.time_taken_seconds / 60, 2)
            }
            for record in sorted(performance_records, key=lambda x: x.timestamp, reverse=True)[:5]
        ]
    }

@app.post("/api/quizzes/{quiz_id}/questions/bulk/")
async def bulk_add_questions(quiz_id: int, questions: List[BulkQuestionCreate], db: Session = Depends(get_db)):
    """
    Bulk add multiple questions to a quiz.
    """
    # Verify the quiz exists
    db_quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    count = 0
    for q in questions:
        # Basic validation for question_type and subsection consistency in bulk data
        valid_types = ["Quant", "Verbal", "Data Insights"]
        if q.question_type not in valid_types:
             raise HTTPException(status_code=400, detail=f"Invalid question_type in bulk data: {q.question_type}. Must be one of {valid_types}")

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
        
        # For Quant and Data Insights, rc_id should also be None
        if q.question_type in ["Quant", "Data Insights"] and q.rc_id is not None:
             raise HTTPException(status_code=400, detail=f"RC Passage link in bulk data must be null for question_type {q.question_type}.")

        # Verify RC passage exists if rc_id is provided in bulk data
        if q.rc_id is not None:
            db_rc_passage = db.query(RCPassageDB).filter(RCPassageDB.id == q.rc_id).first()
            if db_rc_passage is None:
                raise HTTPException(status_code=404, detail=f"RC Passage with ID {q.rc_id} not found for a question in the bulk upload.")
        
        db_question = QuestionDB(
            quiz_id=quiz_id,
            rc_id=q.rc_id, # Save the optional rc_id from bulk data
            question_text=q.questionText,
            options_json=json.dumps(q.options),
            correct_answer=q.correctAnswer,
            answer_explanation=q.answerExplanation, # Save answer explanation from bulk data
            image=None, # Bulk upload currently doesn't support images
            difficulty=q.difficulty,
            question_type=q.question_type, # Save question type from bulk data
            subsection=q.subsection # Save subsection from bulk data
        )
        db.add(db_question)
        count += 1
    
    db.commit()
    return {"message": f"{count} questions added to quiz {quiz_id}."}

# --- User Explanation Endpoints ---

@app.post("/api/performance/{performance_id}/explanations/", response_model=UserExplanationResponse, status_code=201)
async def create_user_explanation(
    performance_id: int,
    explanation: UserExplanationCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update a user explanation for a specific question in a performance record.
    """
    # Verify performance record exists
    performance = db.query(PerformanceDB).filter(PerformanceDB.id == performance_id).first()
    if not performance:
        raise HTTPException(status_code=404, detail="Performance record not found")
    
    # Verify question exists
    question = db.query(QuestionDB).filter(QuestionDB.id == explanation.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Check if explanation already exists for this question
    existing_explanation = db.query(UserExplanationDB).filter(
        UserExplanationDB.performance_id == performance_id,
        UserExplanationDB.question_id == explanation.question_id
    ).first()
    
    if existing_explanation:
        # Update existing explanation
        existing_explanation.explanation_text = explanation.explanation_text
        existing_explanation.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(existing_explanation)
        return existing_explanation
    else:
        # Create new explanation
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
    """
    Get all user explanations for a specific performance record.
    """
    # Verify performance record exists
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
    """
    Get user explanation for a specific question in a performance record.
    """
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
    """
    Update user explanation for a specific question.
    """
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
    """
    Delete user explanation for a specific question.
    """
    explanation = db.query(UserExplanationDB).filter(
        UserExplanationDB.performance_id == performance_id,
        UserExplanationDB.question_id == question_id
    ).first()
    
    if not explanation:
        raise HTTPException(status_code=404, detail="User explanation not found")
    
    db.delete(explanation)
    db.commit()

# Ensure tables are created
Base.metadata.create_all(bind=engine)


