import json
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base, PerformanceDB, DetailedResultDB, UserDB

def migrate_performance_data():
    # Since we have user-specific databases, we need to iterate through them
    db_path = os.path.join("data", "quiz.db")
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}, creating it...")
        main_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(bind=main_engine)
    else:
        main_engine = create_engine(f"sqlite:///{db_path}")

    MainSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=main_engine)
    db = MainSessionLocal()
    try:
        users = db.query(UserDB).all()
    except Exception as e:
        print(f"Error querying users: {e}")
        users = []
    finally:
        db.close()

    for user in users:
        print(f"Migrating data for user {user.id}...")
        user_db_path = UserDB.get_user_db_path(user.id)
        if not os.path.exists(user_db_path):
            print(f"Database not found for user {user.id} at {user_db_path}")
            continue

        user_engine = create_engine(f"sqlite:///{user_db_path}")
        UserSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=user_engine)
        user_db = UserSessionLocal()

        try:
            # Create the new detailed_results table
            Base.metadata.create_all(bind=user_engine, tables=[DetailedResultDB.__table__])

            # Add detailed_results_json column if it doesn't exist
            try:
                user_db.execute(text("ALTER TABLE performance ADD COLUMN detailed_results_json TEXT"))
                user_db.commit()
            except Exception:
                user_db.rollback()


            # Migrate the data
            performances = user_db.query(PerformanceDB).all()
            for p in performances:
                if p.detailed_results_json:
                    try:
                        detailed_results = json.loads(p.detailed_results_json)
                        for result in detailed_results:
                            new_detailed_result = DetailedResultDB(
                                performance_id=p.id,
                                question_id=result.get("questionId"),
                                correct=result.get("correct"),
                                user_answer=result.get("userAnswer"),
                                time_spent=result.get("timeSpent")
                            )
                            user_db.add(new_detailed_result)
                    except (json.JSONDecodeError, TypeError):
                        continue
            user_db.commit()

            # Remove the detailed_results_json column
            try:
                user_db.execute(text("ALTER TABLE performance DROP COLUMN detailed_results_json"))
                user_db.commit()
            except Exception:
                user_db.rollback()

        except Exception as e:
            print(f"Error migrating data for user {user.id}: {e}")
            user_db.rollback()
        finally:
            user_db.close()

    print("Migration completed.")

if __name__ == "__main__":
    migrate_performance_data()
