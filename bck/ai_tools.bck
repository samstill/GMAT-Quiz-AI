# ai_tools.py

import json
from sqlalchemy.orm import Session, joinedload
from models import PerformanceDB, QuestionDB, UserExplanationDB, QuizDB, RCPassageDB
from sqlalchemy import or_, and_, desc, func

# Tool registry for inter-tool communication
_TOOL_REGISTRY = {}
_CALL_STACK = []  # Track call stack to prevent circular dependencies

def register_tool(name: str, func):
    """Register a tool function for inter-tool communication"""
    _TOOL_REGISTRY[name] = func

def call_tool(tool_name: str, db: Session, **kwargs):
    """Call another tool from within a tool function with circular dependency protection"""
    # Check for circular dependencies
    if tool_name in _CALL_STACK:
        return json.dumps({"error": f"Circular dependency detected: {' -> '.join(_CALL_STACK)} -> {tool_name}"})
    
    # Limit call depth to prevent excessive nesting
    if len(_CALL_STACK) > 3:
        return json.dumps({"error": f"Maximum call depth exceeded. Call stack: {' -> '.join(_CALL_STACK)}"})
    
    if tool_name in _TOOL_REGISTRY:
        _CALL_STACK.append(tool_name)
        try:
            result = _TOOL_REGISTRY[tool_name](db=db, **kwargs)
            return result
        finally:
            _CALL_STACK.pop()
    else:
        return json.dumps({"error": f"Tool '{tool_name}' not found in registry"})

def parse_tool_result(tool_result: str):
    """Parse the JSON result from another tool call"""
    try:
        return json.loads(tool_result)
    except json.JSONDecodeError:
        return {"error": "Failed to parse tool result"}

# Decorator to auto-register tools
def tool(name: str):
    def decorator(func):
        register_tool(name, func)
        return func
    return decorator

@tool("get_performance_summary")
def get_performance_summary(db: Session, quiz_id: int = None, quiz_name: str = None):
    """
    Analyzes all performance records to provide a high-level summary.
    If quiz_id or quiz_name is provided, filters the summary for that specific quiz.
    If neither is provided, analyzes performance across all quizzes.
    Can call other tools for enhanced analysis.
    """
    # Resolve quiz name to quiz ID if provided
    resolved_quiz_id = quiz_id
    if quiz_name and not quiz_id:
        resolved_quiz_id = resolve_quiz_identifier(db, quiz_name)
        if resolved_quiz_id is None:
            return json.dumps({
                "error": f"Quiz '{quiz_name}' not found.",
                "suggestion": "Please check the quiz name and try again."
            })
    
    query = db.query(PerformanceDB).options(joinedload(PerformanceDB.quiz))
    
    # If specific quiz_id is provided, filter for it
    if resolved_quiz_id:
        query = query.filter(PerformanceDB.quiz_id == resolved_quiz_id)
        quiz_context = f"Quiz {resolved_quiz_id}"
        
        # Get quiz details directly from database to avoid circular dependency
        quiz_obj = db.query(QuizDB).filter(QuizDB.id == resolved_quiz_id).first()
        quiz_info = {
            "id": quiz_obj.id,
            "name": quiz_obj.name,
            "timeLimitMinutes": quiz_obj.time_limit_minutes
        } if quiz_obj else None
    else:
        quiz_context = "All Quizzes"
        quiz_info = None
    
    records = query.all()
    if not records:
        # If specific quiz_id was provided but no data found, check if quiz exists and provide alternatives
        if resolved_quiz_id:
            quiz_obj = db.query(QuizDB).filter(QuizDB.id == resolved_quiz_id).first()
            if quiz_obj:
                # Quiz exists but no performance data - show available alternatives
                available_performances = (db.query(PerformanceDB)
                                        .options(joinedload(PerformanceDB.quiz))
                                        .order_by(PerformanceDB.timestamp.desc())
                                        .limit(5).all())
                
                if available_performances:
                    recent_quizzes = []
                    for perf in available_performances:
                        accuracy = f"{(perf.correct_answers / perf.total_questions * 100):.1f}%" if perf.total_questions > 0 else "N/A"
                        recent_quizzes.append({
                            "quizId": perf.quiz_id,
                            "quizName": perf.quiz.name if perf.quiz else "Unknown",
                            "accuracy": accuracy,
                            "timestamp": perf.timestamp.isoformat() if perf.timestamp else None
                        })
                    
                    return json.dumps({
                        "message": f"Quiz {resolved_quiz_id} ('{quiz_obj.name}') exists but you haven't taken it yet.",
                        "suggestion": "Would you like to see performance for a quiz you've actually taken?",
                        "recentQuizPerformances": recent_quizzes[:3],
                        "quizRequested": {
                            "id": resolved_quiz_id,
                            "name": quiz_obj.name,
                            "status": "Not attempted yet"
                        }
                    })
                else:
                    return json.dumps({
                        "message": f"Quiz {resolved_quiz_id} ('{quiz_obj.name}') exists but you haven't taken it yet.",
                        "suggestion": "Take some quizzes first to see your performance data!"
                    })
            else:
                return json.dumps({"message": f"Quiz {resolved_quiz_id} does not exist."})
        else:
            return json.dumps({"message": f"No performance data found for {quiz_context.lower()}."})

    total_correct = sum(r.correct_answers for r in records)
    total_questions = sum(r.total_questions for r in records)
    overall_accuracy = f"{(total_correct / total_questions * 100):.1f}%" if total_questions > 0 else "N/A"

    # Get performance breakdown by calling another tool
    performance_breakdown = parse_tool_result(call_tool("get_performance_by_question_type_and_difficulty", db))

    summary = {
        "context": quiz_context,
        "quizInfo": quiz_info,
        "totalAttempts": len(records),
        "overallAccuracy": overall_accuracy,
        "totalQuestionsAttempted": total_questions,
        "totalCorrectAnswers": total_correct,
        "performanceBreakdown": performance_breakdown.get("performanceBreakdown", [])
    }
    return json.dumps(summary, indent=2)


@tool("get_most_recent_incorrect_answers")
def get_most_recent_incorrect_answers(db: Session, quiz_id: int = None, quiz_name: str = None, limit: int = 5):
    """
    Retrieves details for the most recent questions the user answered incorrectly.
    If quiz_id or quiz_name is provided, filters for that specific quiz. 
    If neither is provided, finds incorrect answers from the most recent performance overall.
    This helps the AI give specific, actionable feedback.
    Can call other tools to get additional context.
    """
    # Resolve quiz name to quiz ID if provided
    resolved_quiz_id = quiz_id
    if quiz_name and not quiz_id:
        resolved_quiz_id = resolve_quiz_identifier(db, quiz_name)
        if resolved_quiz_id is None:
            return json.dumps({
                "error": f"Quiz '{quiz_name}' not found.",
                "suggestion": "Please check the quiz name and try again."
            })
    
    query = db.query(PerformanceDB).order_by(PerformanceDB.timestamp.desc())
    
    # If specific quiz_id is provided, filter for it
    if resolved_quiz_id:
        query = query.filter(PerformanceDB.quiz_id == resolved_quiz_id)
        context = f"quiz {resolved_quiz_id}"
    else:
        context = "recent attempts"
    
    latest_performance = query.first()
    if not latest_performance or not latest_performance.detailed_results_json:
        # If specific quiz_id was provided but no data found, check if quiz exists and provide helpful alternatives
        if resolved_quiz_id:
            quiz_exists = db.query(QuizDB).filter(QuizDB.id == resolved_quiz_id).first()
            if quiz_exists:
                # Quiz exists but no performance data - offer alternatives
                available_quiz_performances = (db.query(PerformanceDB)
                                             .options(joinedload(PerformanceDB.quiz))
                                             .order_by(PerformanceDB.timestamp.desc())
                                             .limit(5).all())
                
                if available_quiz_performances:
                    suggestions = []
                    for perf in available_quiz_performances:
                        if perf.detailed_results_json:
                            detailed = json.loads(perf.detailed_results_json)
                            incorrect_count = len([q for q in detailed if not q.get('correct')])
                            if incorrect_count > 0:
                                suggestions.append({
                                    "quizId": perf.quiz_id,
                                    "quizName": perf.quiz.name if perf.quiz else "Unknown",
                                    "incorrectAnswers": incorrect_count,
                                    "timestamp": perf.timestamp.isoformat() if perf.timestamp else None
                                })
                    
                    return json.dumps({
                        "message": f"Quiz {resolved_quiz_id} ('{quiz_exists.name}') exists but you haven't taken it yet. No performance data available for this quiz.",
                        "suggestion": "Would you like to see incorrect answers from a quiz you've actually taken?",
                        "availableQuizzesWithIncorrectAnswers": suggestions[:3],
                        "quizRequested": {
                            "id": resolved_quiz_id,
                            "name": quiz_exists.name,
                            "status": "Not attempted yet"
                        }
                    })
                else:
                    return json.dumps({
                        "message": f"Quiz {resolved_quiz_id} ('{quiz_exists.name}') exists but you haven't taken it yet.",
                        "suggestion": "Take the quiz first to see your incorrect answers!"
                    })
            else:
                return json.dumps({"message": f"Quiz {resolved_quiz_id} does not exist."})
        else:
            return json.dumps({"message": f"No recent performance data with incorrect answers found for {context}."})
        
    detailed_results = json.loads(latest_performance.detailed_results_json)
    incorrect_answers = [q for q in detailed_results if not q.get('correct')]

    if not incorrect_answers:
        return json.dumps({"message": f"No incorrect answers found in the most recent performance for {context}."})

    # Trim down the response to avoid making it too large
    trimmed_results = []
    for q in incorrect_answers[:limit]:
        # Fetch the user explanation for this specific question and performance record
        user_explanation = db.query(UserExplanationDB).filter(
            UserExplanationDB.performance_id == latest_performance.id,
            UserExplanationDB.question_id == q.get("questionId")
        ).first()

        # Get additional question context by searching for the question
        question_details = parse_tool_result(call_tool("search_questions_by_text", db, 
                                                      search_text=q.get("questionText", "")[:50], 
                                                      limit=1))

        trimmed_results.append({
            "questionId": q.get("questionId"),
            "questionText": q.get("questionText"),
            "userAnswer": q.get("userAnswer"),
            "correctAnswer": q.get("correctAnswer"),
            "answerExplanation": q.get("answerExplanation"), # Official explanation
            "question_type": q.get("question_type"),
            "difficulty": q.get("difficulty"),
            "userExplanation": user_explanation.explanation_text if user_explanation else None, # Your explanation
            "additionalContext": question_details.get("questions", [])
        })

    # Get quiz information if available
    quiz_info = None
    if latest_performance.quiz_id:
        quiz_data = parse_tool_result(call_tool("get_all_quizzes", db))
        if "quizzes" in quiz_data:
            quiz_info = next((q for q in quiz_data["quizzes"] if q["id"] == latest_performance.quiz_id), None)

    return json.dumps({
        "context": context,
        "performanceId": latest_performance.id,
        "quizInfo": quiz_info,
        "quizName": latest_performance.quiz.name if latest_performance.quiz else "Unknown",
        "incorrectAnswers": trimmed_results
    }, indent=2)


@tool("get_all_quizzes")
def get_all_quizzes(db: Session):
    """
    Retrieves all available quizzes with their basic information.
    Useful for understanding what quiz options are available.
    Enhanced with performance data from other tools.
    """
    quizzes = db.query(QuizDB).all()
    if not quizzes:
        return json.dumps({"message": "No quizzes found in the database."})
    
    quiz_data = []
    for quiz in quizzes:
        question_count = db.query(QuestionDB).filter(QuestionDB.quiz_id == quiz.id).count()
        
        # Get performance summary for this specific quiz
        performance_data = parse_tool_result(call_tool("get_performance_summary", db, quiz_id=quiz.id))
        
        quiz_info = {
            "id": quiz.id,
            "name": quiz.name,
            "timeLimitMinutes": quiz.time_limit_minutes,
            "questionCount": question_count
        }
        
        # Add performance data if available
        if "totalAttempts" in performance_data:
            quiz_info["performanceSummary"] = {
                "totalAttempts": performance_data.get("totalAttempts", 0),
                "overallAccuracy": performance_data.get("overallAccuracy", "N/A")
            }
        
        quiz_data.append(quiz_info)
    
    return json.dumps({"quizzes": quiz_data}, indent=2)


@tool("get_quiz_questions")
def get_quiz_questions(db: Session, quiz_id: int = None, include_rc_passages: bool = True):
    """
    Retrieves questions from quizzes. If quiz_id is provided, gets questions from that specific quiz.
    If no quiz_id is provided, automatically selects the most recent or available quiz.
    Provides complete question data for detailed analysis.
    Enhanced with cross-references to performance data.
    """
    if quiz_id is None:
        # Auto-select the most recently created quiz or the first available quiz
        quiz = db.query(QuizDB).order_by(QuizDB.id.desc()).first()
        if not quiz:
            return json.dumps({"message": "No quizzes found in the database."})
        quiz_id = quiz.id
    else:
        quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
        if not quiz:
            return json.dumps({"message": f"Quiz with ID {quiz_id} not found."})
    
    query = db.query(QuestionDB).filter(QuestionDB.quiz_id == quiz_id)
    if include_rc_passages:
        query = query.options(joinedload(QuestionDB.rc_passage))
    
    questions = query.all()
    
    # Get performance data for this quiz to enhance question information
    performance_data = parse_tool_result(call_tool("get_performance_summary", db, quiz_id=quiz_id))
    
    question_data = []
    for q in questions:
        question_info = {
            "id": q.id,
            "questionText": q.question_text,
            "options": json.loads(q.options_json) if q.options_json else {},
            "correctAnswer": q.correct_answer,
            "answerExplanation": q.answer_explanation,
            "difficulty": q.difficulty,
            "questionType": q.question_type,
            "subsection": q.subsection,
            "image": q.image
        }
        
        if q.rc_passage and include_rc_passages:
            question_info["rcPassage"] = {
                "id": q.rc_passage.id,
                "passage": q.rc_passage.passage_text,
                "title": q.rc_passage.title
            }
        
        question_data.append(question_info)
    
    return json.dumps({
        "quizId": quiz_id,
        "quizName": quiz.name,
        "questions": question_data,
        "totalQuestions": len(question_data)
    }, indent=2)


@tool("get_quizzes_sorted_by_date")
def get_quizzes_sorted_by_date(db: Session, ascending: bool = False, limit: int = None):
    """
    Retrieves all quiz performances sorted by the date they were taken.
    By default returns newest first (descending), but can be changed with ascending=True.
    Useful for finding the most recent or oldest quiz attempts.
    """
    query = db.query(PerformanceDB).options(joinedload(PerformanceDB.quiz))
    
    if ascending:
        query = query.order_by(PerformanceDB.timestamp.asc())
    else:
        query = query.order_by(PerformanceDB.timestamp.desc())
    
    if limit:
        query = query.limit(limit)
    
    performances = query.all()
    
    if not performances:
        return json.dumps({"message": "No quiz performances found in the database."})
    
    quiz_data = []
    for perf in performances:
        quiz_info = {
            "performanceId": perf.id,
            "quizId": perf.quiz_id,
            "quizName": perf.quiz.name if perf.quiz else "Unknown",
            "dateTaken": perf.timestamp.isoformat() if perf.timestamp else None,
            "totalQuestions": perf.total_questions,
            "correctAnswers": perf.correct_answers,
            "accuracy": f"{(perf.correct_answers / perf.total_questions * 100):.1f}%" if perf.total_questions > 0 else "N/A",
            "timeTakenSeconds": perf.time_taken_seconds
        }
        
        # Add performance breakdown if available
        if perf.detailed_results_json:
            detailed_results = json.loads(perf.detailed_results_json)
            breakdown = {}
            for result in detailed_results:
                q_type = result.get('questionType', 'Unknown')
                difficulty = result.get('difficulty', 'Unknown')
                key = f"{q_type}_{difficulty}"
                
                if key not in breakdown:
                    breakdown[key] = {"total": 0, "correct": 0}
                
                breakdown[key]["total"] += 1
                if result.get('correct'):
                    breakdown[key]["correct"] += 1
            
            quiz_info["performanceBreakdown"] = breakdown
        
        quiz_data.append(quiz_info)
    
    sort_order = "oldest to newest" if ascending else "newest to oldest"
    return json.dumps({
        "quizzes": quiz_data,
        "totalAttempts": len(quiz_data),
        "sortOrder": sort_order,
        "limitApplied": limit
    }, indent=2)


@tool("get_most_recent_quiz_performance")
def get_most_recent_quiz_performance(db: Session):
    """
    Gets detailed performance data for the most recent quiz attempt.
    This is specifically useful for analyzing the latest performance.
    """
    latest_performance = (db.query(PerformanceDB)
                         .options(joinedload(PerformanceDB.quiz))
                         .order_by(PerformanceDB.timestamp.desc())
                         .first())
    
    if not latest_performance:
        return json.dumps({"message": "No quiz performances found in the database."})
    
    # Get detailed analysis using existing tools
    performance_summary = parse_tool_result(call_tool("get_performance_summary", db, quiz_id=latest_performance.quiz_id))
    recent_incorrect = parse_tool_result(call_tool("get_most_recent_incorrect_answers", db, quiz_id=latest_performance.quiz_id))
    
    result = {
        "mostRecentQuiz": {
            "performanceId": latest_performance.id,
            "quizId": latest_performance.quiz_id,
            "quizName": latest_performance.quiz.name if latest_performance.quiz else "Unknown",
            "dateTaken": latest_performance.timestamp.isoformat() if latest_performance.timestamp else None,
            "totalQuestions": latest_performance.total_questions,
            "correctAnswers": latest_performance.correct_answers,
            "accuracy": f"{(latest_performance.correct_answers / latest_performance.total_questions * 100):.1f}%" if latest_performance.total_questions > 0 else "N/A",
            "timeTakenSeconds": latest_performance.time_taken_seconds
        },
        "detailedAnalysis": performance_summary,
        "recentMistakes": recent_incorrect
    }
    
    return json.dumps(result, indent=2)


@tool("get_performance_by_question_type_and_difficulty")
def get_performance_by_question_type_and_difficulty(db: Session, quiz_id: int = None):
    """
    Provides detailed performance breakdown by question type and difficulty level.
    Useful for identifying specific areas of strength and weakness.
    """
    query = db.query(PerformanceDB)
    if quiz_id:
        query = query.filter(PerformanceDB.quiz_id == quiz_id)
    
    performances = query.all()
    
    if not performances:
        return json.dumps({"performanceBreakdown": []})
    
    # Initialize breakdown structure
    breakdown = {}
    
    for perf in performances:
        if perf.detailed_results_json:
            try:
                detailed_results = json.loads(perf.detailed_results_json)
                for result in detailed_results:
                    q_type = result.get('questionType', result.get('question_type', 'Unknown'))
                    difficulty = result.get('difficulty', 'Unknown')
                    correct = result.get('correct', False)
                    
                    # Create nested structure: type -> difficulty
                    if q_type not in breakdown:
                        breakdown[q_type] = {}
                    
                    if difficulty not in breakdown[q_type]:
                        breakdown[q_type][difficulty] = {"total": 0, "correct": 0}
                    
                    breakdown[q_type][difficulty]["total"] += 1
                    if correct:
                        breakdown[q_type][difficulty]["correct"] += 1
            except json.JSONDecodeError:
                continue
    
    # Calculate percentages and create summary
    formatted_breakdown = []
    for q_type, difficulties in breakdown.items():
        type_summary = {
            "questionType": q_type,
            "byDifficulty": {}
        }
        
        type_total = 0
        type_correct = 0
        
        for difficulty, stats in difficulties.items():
            percentage = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
            type_summary["byDifficulty"][difficulty] = {
                "total": stats["total"],
                "correct": stats["correct"],
                "accuracy": f"{percentage:.1f}%"
            }
            type_total += stats["total"]
            type_correct += stats["correct"]
        
        # Add overall type performance
        type_percentage = (type_correct / type_total * 100) if type_total > 0 else 0
        type_summary["overall"] = {
            "total": type_total,
            "correct": type_correct,
            "accuracy": f"{type_percentage:.1f}%"
        }
        
        formatted_breakdown.append(type_summary)
    
    return json.dumps({"performanceBreakdown": formatted_breakdown}, indent=2)


@tool("analyze_latest_quiz_detailed")
def analyze_latest_quiz_detailed(db: Session):
    """
    Provides comprehensive question-by-question analysis of the most recent quiz performance.
    This tool focuses ONLY on the latest quiz attempt and provides detailed insights.
    Perfect for answering "How did I do on my recent quiz?"
    """
    # Get the most recent performance
    latest_performance = (db.query(PerformanceDB)
                         .options(joinedload(PerformanceDB.quiz))
                         .order_by(PerformanceDB.timestamp.desc())
                         .first())
    
    if not latest_performance:
        return json.dumps({"message": "No quiz performances found in the database."})
    
    if not latest_performance.detailed_results_json:
        return json.dumps({
            "message": "No detailed results available for the most recent quiz.",
            "basicInfo": {
                "quizName": latest_performance.quiz.name if latest_performance.quiz else "Unknown",
                "score": f"{latest_performance.correct_answers}/{latest_performance.total_questions}",
                "dateTaken": latest_performance.timestamp.isoformat() if latest_performance.timestamp else None
            }
        })
    
    try:
        detailed_results = json.loads(latest_performance.detailed_results_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Could not parse detailed results for the most recent quiz."})
    
    # Analyze the results
    correct_answers = []
    incorrect_answers = []
    question_type_performance = {}
    difficulty_performance = {}
    time_analysis = []
    
    for result in detailed_results:
        question_info = {
            "questionId": result.get("questionId"),
            "questionText": result.get("questionText", "")[:200] + "..." if len(result.get("questionText", "")) > 200 else result.get("questionText", ""),
            "correct": result.get("correct", False),
            "userAnswer": result.get("userAnswer"),
            "correctAnswer": result.get("correctAnswer"),
            "questionType": result.get("questionType", result.get("question_type", "Unknown")),
            "difficulty": result.get("difficulty", "Unknown"),
            "timeSpent": result.get("timeSpent"),
            "answerExplanation": result.get("answerExplanation", ""),
            "subsection": result.get("subsection")
        }
        
        # Categorize by correctness
        if result.get("correct"):
            correct_answers.append(question_info)
        else:
            incorrect_answers.append(question_info)
        
        # Track performance by question type
        q_type = question_info["questionType"]
        if q_type not in question_type_performance:
            question_type_performance[q_type] = {"correct": 0, "total": 0}
        question_type_performance[q_type]["total"] += 1
        if result.get("correct"):
            question_type_performance[q_type]["correct"] += 1
        
        # Track performance by difficulty
        difficulty = question_info["difficulty"]
        if difficulty not in difficulty_performance:
            difficulty_performance[difficulty] = {"correct": 0, "total": 0}
        difficulty_performance[difficulty]["total"] += 1
        if result.get("correct"):
            difficulty_performance[difficulty]["correct"] += 1
        
        # Time analysis
        if question_info["timeSpent"]:
            time_analysis.append({
                "questionId": question_info["questionId"],
                "timeSpent": question_info["timeSpent"],
                "correct": question_info["correct"],
                "difficulty": question_info["difficulty"]
            })
    
    # Calculate performance percentages
    for q_type in question_type_performance:
        stats = question_type_performance[q_type]
        stats["accuracy"] = f"{(stats['correct'] / stats['total'] * 100):.1f}%" if stats['total'] > 0 else "N/A"
    
    for difficulty in difficulty_performance:
        stats = difficulty_performance[difficulty]
        stats["accuracy"] = f"{(stats['correct'] / stats['total'] * 100):.1f}%" if stats['total'] > 0 else "N/A"
    
    # Get user explanations for incorrect answers
    incorrect_with_explanations = []
    for incorrect in incorrect_answers:
        user_explanation = db.query(UserExplanationDB).filter(
            UserExplanationDB.performance_id == latest_performance.id,
            UserExplanationDB.question_id == incorrect["questionId"]
        ).first()
        
        incorrect_detail = incorrect.copy()
        incorrect_detail["userExplanation"] = user_explanation.explanation_text if user_explanation else None
        incorrect_with_explanations.append(incorrect_detail)
    
    # Identify patterns in mistakes
    mistake_patterns = {}
    for mistake in incorrect_answers:
        pattern_key = f"{mistake['questionType']}_{mistake['difficulty']}"
        if pattern_key not in mistake_patterns:
            mistake_patterns[pattern_key] = 0
        mistake_patterns[pattern_key] += 1
    
    # Time insights
    time_insights = {}
    if time_analysis:
        avg_time_correct = sum([t["timeSpent"] for t in time_analysis if t["correct"]]) / len([t for t in time_analysis if t["correct"]]) if [t for t in time_analysis if t["correct"]] else 0
        avg_time_incorrect = sum([t["timeSpent"] for t in time_analysis if not t["correct"]]) / len([t for t in time_analysis if not t["correct"]]) if [t for t in time_analysis if not t["correct"]] else 0
        
        time_insights = {
            "averageTimeOnCorrectAnswers": f"{avg_time_correct:.1f} seconds" if avg_time_correct > 0 else "N/A",
            "averageTimeOnIncorrectAnswers": f"{avg_time_incorrect:.1f} seconds" if avg_time_incorrect > 0 else "N/A",
            "totalTimeSpent": f"{sum([t['timeSpent'] for t in time_analysis]):.1f} seconds" if time_analysis else "N/A"
        }
    
    result = {
        "quizOverview": {
            "quizName": latest_performance.quiz.name if latest_performance.quiz else "Unknown",
            "dateTaken": latest_performance.timestamp.isoformat() if latest_performance.timestamp else None,
            "totalQuestions": latest_performance.total_questions,
            "correctAnswers": latest_performance.correct_answers,
            "incorrectAnswers": latest_performance.total_questions - latest_performance.correct_answers,
            "overallAccuracy": f"{(latest_performance.correct_answers / latest_performance.total_questions * 100):.1f}%" if latest_performance.total_questions > 0 else "N/A",
            "timeTaken": f"{latest_performance.time_taken_seconds} seconds"
        },
        "performanceByQuestionType": question_type_performance,
        "performanceByDifficulty": difficulty_performance,
        "correctAnswersDetails": correct_answers[:5],  # Show first 5 correct answers
        "incorrectAnswersDetails": incorrect_with_explanations,  # Show all incorrect answers with explanations
        "mistakePatterns": mistake_patterns,
        "timeInsights": time_insights,
        "keyInsights": {
            "strongestArea": max(question_type_performance.items(), key=lambda x: x[1]["correct"]/x[1]["total"] if x[1]["total"] > 0 else 0)[0] if question_type_performance else "N/A",
            "weakestArea": min(question_type_performance.items(), key=lambda x: x[1]["correct"]/x[1]["total"] if x[1]["total"] > 0 else 1)[0] if question_type_performance else "N/A",
            "mostMissedDifficulty": max(difficulty_performance.items(), key=lambda x: x[1]["total"] - x[1]["correct"] if x[1]["total"] > 0 else 0)[0] if difficulty_performance else "N/A"
        }
    }
    
    return json.dumps(result, indent=2)
# Export the tool registry as AVAILABLE_TOOLS for main.py
AVAILABLE_TOOLS = _TOOL_REGISTRY

# Gemini API tool definitions for function calling
GEMINI_TOOLS = [
    {
        "name": "get_performance_summary",
        "description": "Get overall performance summary for a specific quiz or all quizzes. Provides detailed statistics including accuracy, question type breakdown, and difficulty analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "quiz_id": {"type": "integer", "description": "Optional quiz ID to filter results"},
                "quiz_name": {"type": "string", "description": "Optional quiz name to filter results (alternative to quiz_id)"}
            }
        }
    },
    {
        "name": "get_most_recent_incorrect_answers",
        "description": "Get detailed information about recent incorrect answers, useful for identifying patterns and areas for improvement.",
        "parameters": {
            "type": "object",
            "properties": {
                "quiz_id": {"type": "integer", "description": "Optional quiz ID to filter results"},
                "quiz_name": {"type": "string", "description": "Optional quiz name to filter results"},
                "limit": {"type": "integer", "description": "Maximum number of incorrect answers to return (default 5)"}
            }
        }
    },
    {
        "name": "get_all_quizzes",
        "description": "Get list of all available quizzes with basic information and performance statistics.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_quiz_questions",
        "description": "Get detailed question information for a specific quiz, including content, options, correct answers, and RC passages.",
        "parameters": {
            "type": "object",
            "properties": {
                "quiz_id": {"type": "integer", "description": "Optional quiz ID (if not provided, uses most recent quiz)"},
                "include_rc_passages": {"type": "boolean", "description": "Whether to include RC passage content (default true)"}
            }
        }
    },
    {
        "name": "get_quizzes_sorted_by_date",
        "description": "Get all quiz performances sorted by the date they were taken. Perfect for identifying the most recent or oldest quiz attempts.",
        "parameters": {
            "type": "object",
            "properties": {
                "ascending": {"type": "boolean", "description": "If true, sorts oldest to newest. If false (default), sorts newest to oldest"},
                "limit": {"type": "integer", "description": "Optional limit on number of results to return"}
            }
        }
    },
    {
        "name": "get_most_recent_quiz_performance",
        "description": "Get comprehensive analysis of the most recent quiz attempt with detailed performance data.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_performance_by_question_type_and_difficulty",
        "description": "Get detailed performance breakdown by question type and difficulty level, useful for identifying specific strengths and weaknesses.",
        "parameters": {
            "type": "object",
            "properties": {
                "quiz_id": {"type": "integer", "description": "Optional quiz ID to filter results"}
            }
        }
    },
    {
        "name": "analyze_latest_quiz_detailed",
        "description": "Provides comprehensive question-by-question analysis of the MOST RECENT quiz performance ONLY. Use this when user asks specifically about their latest/recent quiz performance, mistakes, or wants detailed analysis of their most recent attempt.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_performance_by_question_type_and_difficulty",
        "description": "Get detailed performance breakdown by question type and difficulty level. Useful for identifying specific areas of strength and weakness.",
        "parameters": {
            "type": "object",
            "properties": {
                "quiz_id": {"type": "integer", "description": "Optional quiz ID to filter results"}
            }
        }
    },
    {
        "name": "analyze_latest_quiz_detailed",
        "description": "Get a detailed, question-by-question analysis of the most recent quiz performance. Ideal for understanding strengths and weaknesses on the latest quiz attempt.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]

# Gemini tool configuration
GEMINI_TOOL_CONFIG = {
    "function_calling_config": {
        "mode": "AUTO"
    }
}