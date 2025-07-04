import os
import shutil
import sqlite3
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import Base, UserDB, QuizDB, QuestionDB, PerformanceDB, UserExplanationDB, FlashcardSetDB, IndividualFlashcardDB, RCPassageDB

# Main database setup
MAIN_DATABASE_URL = "sqlite:///./quiz.db"
main_engine = create_engine(MAIN_DATABASE_URL, connect_args={"check_same_thread": False})
MainSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=main_engine)

def migrate_user_data():
    """
    Migrate data from main database to user-specific databases.
    This will:
    1. Ensure each user has a database
    2. Migrate quizzes, questions, performance data, etc. to each user's database
    """
    print("Starting user data migration...")
    
    # Create user_databases directory if it doesn't exist
    os.makedirs('user_databases', exist_ok=True)
    
    # Get all active users
    main_db = MainSessionLocal()
    try:
        users = main_db.query(UserDB).filter(UserDB.is_active == True).all()
        print(f"Found {len(users)} active users to migrate data for")
        
        for user in users:
            print(f"Processing user {user.username} (ID: {user.id})...")
            
            # Ensure user has a database path
            if not user.database_path:
                user_db_path = UserDB.create_user_db(user.id)
                user.database_path = user_db_path
                main_db.commit()
            else:
                # Make sure the database file exists
                if not os.path.exists(user.database_path):
                    UserDB.create_user_db(user.id)
            
            # Get user's engine and session
            user_engine = create_engine(f"sqlite:///{user.database_path}", connect_args={"check_same_thread": False})
            UserSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=user_engine)
            user_db = UserSessionLocal()
            
            try:
                # Migrate quizzes
                quizzes = main_db.query(QuizDB).filter(QuizDB.created_by_user_id == user.id).all()
                print(f"Found {len(quizzes)} quizzes to migrate for user {user.username}")
                
                for quiz in quizzes:
                    # Check if quiz already exists in user db
                    existing_quiz = user_db.query(QuizDB).filter(QuizDB.id == quiz.id).first()
                    if not existing_quiz:
                        # Create new quiz in user db
                        new_quiz = QuizDB(
                            id=quiz.id,
                            name=quiz.name,
                            time_limit_minutes=quiz.time_limit_minutes,
                            created_by_user_id=quiz.created_by_user_id
                        )
                        user_db.add(new_quiz)
                        user_db.commit()
                        
                        # Migrate questions for this quiz
                        questions = main_db.query(QuestionDB).filter(QuestionDB.quiz_id == quiz.id).all()
                        print(f"Migrating {len(questions)} questions for quiz '{quiz.name}'")
                        
                        # Collect RC passages we need to migrate
                        rc_passage_ids = set()
                        for question in questions:
                            if question.rc_id:
                                rc_passage_ids.add(question.rc_id)
                        
                        # Migrate RC passages
                        for rc_id in rc_passage_ids:
                            rc_passage = main_db.query(RCPassageDB).filter(RCPassageDB.id == rc_id).first()
                            if rc_passage:
                                new_rc = RCPassageDB(
                                    id=rc_passage.id,
                                    title=rc_passage.title,
                                    passage_text=rc_passage.passage_text
                                )
                                user_db.add(new_rc)
                        
                        user_db.commit()
                        
                        # Migrate questions
                        for question in questions:
                            new_question = QuestionDB(
                                id=question.id,
                                quiz_id=question.quiz_id,
                                rc_id=question.rc_id,
                                question_text=question.question_text,
                                options_json=question.options_json,
                                correct_answer=question.correct_answer,
                                answer_explanation=question.answer_explanation,
                                image=question.image,
                                difficulty=question.difficulty,
                                question_type=question.question_type,
                                subsection=question.subsection
                            )
                            user_db.add(new_question)
                        
                        user_db.commit()
                        
                        # Migrate performance records
                        performances = main_db.query(PerformanceDB).filter(PerformanceDB.quiz_id == quiz.id).all()
                        print(f"Migrating {len(performances)} performance records for quiz '{quiz.name}'")
                        
                        for perf in performances:
                            new_perf = PerformanceDB(
                                id=perf.id,
                                quiz_id=perf.quiz_id,
                                timestamp=perf.timestamp,
                                total_questions=perf.total_questions,
                                correct_answers=perf.correct_answers,
                                time_taken_seconds=perf.time_taken_seconds,
                                detailed_results_json=perf.detailed_results_json
                            )
                            user_db.add(new_perf)
                            
                            # Migrate user explanations
                            explanations = main_db.query(UserExplanationDB).filter(
                                UserExplanationDB.performance_id == perf.id
                            ).all()
                            
                            for expl in explanations:
                                new_expl = UserExplanationDB(
                                    id=expl.id,
                                    performance_id=expl.performance_id,
                                    question_id=expl.question_id,
                                    explanation_text=expl.explanation_text,
                                    created_at=expl.created_at,
                                    updated_at=expl.updated_at
                                )
                                user_db.add(new_expl)
                            
                        user_db.commit()
                
                # Migrate flashcard sets
                flashcard_sets = main_db.query(FlashcardSetDB).all()
                for fs in flashcard_sets:
                    # Check if set already exists in user db
                    existing_fs = user_db.query(FlashcardSetDB).filter(FlashcardSetDB.id == fs.id).first()
                    if not existing_fs:
                        new_fs = FlashcardSetDB(
                            id=fs.id,
                            name=fs.name,
                            topics=fs.topics,
                            flashcards_json=fs.flashcards_json,
                            created_at=fs.created_at
                        )
                        user_db.add(new_fs)
                
                # Migrate individual flashcards
                individual_cards = main_db.query(IndividualFlashcardDB).all()
                for card in individual_cards:
                    # Check if card already exists in user db
                    existing_card = user_db.query(IndividualFlashcardDB).filter(
                        IndividualFlashcardDB.id == card.id
                    ).first()
                    if not existing_card:
                        new_card = IndividualFlashcardDB(
                            id=card.id,
                            name=card.name,
                            topics=card.topics,
                            flashcard_json=card.flashcard_json,
                            created_at=card.created_at
                        )
                        user_db.add(new_card)
                
                user_db.commit()
                print(f"Successfully migrated data for user {user.username}")
                
            except Exception as e:
                user_db.rollback()
                print(f"Error migrating data for user {user.username}: {str(e)}")
            finally:
                user_db.close()
        
    except Exception as e:
        print(f"Migration error: {str(e)}")
    finally:
        main_db.close()
    
    print("User data migration completed")

if __name__ == "__main__":
    # First, make sure the password column migration is complete
    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        
        # Check if the users table has a 'password' column
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        has_password = any(col[1] == 'password' for col in columns)
        
        if not has_password:
            print("ERROR: The users table does not have a 'password' column.")
            print("Please run migrate_db.py first to migrate from hashed_password to password.")
            exit(1)
        
        conn.close()
    except Exception as e:
        print(f"Error checking database schema: {str(e)}")
        exit(1)
    
    # Run the migration
    migrate_user_data()
