# ai_tools.py

import json
import csv
import os
import io
import httpx
import time
from datetime import datetime
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
    if tool_name in _CALL_STACK:
        return json.dumps({"error": f"Circular dependency detected: {' -> '.join(_CALL_STACK)} -> {tool_name}"})
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

def tool(name: str):
    def decorator(func):
        register_tool(name, func)
        return func
    return decorator

def resolve_quiz_identifier(db: Session, quiz_identifier: str) -> int:
    """Helper to resolve a quiz name or ID to a quiz ID."""
    quiz = db.query(QuizDB).filter(or_(QuizDB.name == quiz_identifier, QuizDB.id == quiz_identifier)).first()
    return quiz.id if quiz else None


def call_gemini_for_question_analysis(question_text: str, api_key: str):
    """
    Makes a synchronous call to the Gemini API to generate a topic, 
    fundamental skill, content area, and in-depth concept for a question.
    """
    if not api_key:
        return {"topic": "Error: API Key Missing", "skill": "Error", "area": "Error", "concept": "Error"}

    # CORRECTED THE URL HERE
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    prompt = f"""
    Analyze the following GMAT question and provide a detailed breakdown.
    Return a single JSON object with four keys: "topic", "skill", "area", and "concept".
    - "topic": A specific, granular topic (e.g., 'Systems of Linear Equations', 'Weaken the Argument').
    - "skill": The fundamental skill tested from the GMAT report list (e.g., 'Rates/Ratios/Percent', 'Identify Inferred Idea').
    - "area": The high-level content area from the GMAT report (e.g., 'Algebra', 'Critical Reasoning').
    - "concept": A detailed, in-depth explanation of the core concept being tested in the question. This should be a few sentences long.

    Question: \"{question_text}\"
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # Extract and clean the JSON string from the response
            response_text = result["candidates"][0]["content"]["parts"][0]["text"]
            # Clean the response to ensure it's valid JSON
            clean_json_str = response_text.strip().replace('```json', '').replace('```', '').strip()
            
            analysis_json = json.loads(clean_json_str)
            
            return {
                "topic": analysis_json.get("topic", "AI Topic Failed"),
                "skill": analysis_json.get("skill", "AI Skill Failed"),
                "area": analysis_json.get("area", "AI Area Failed"),
                "concept": analysis_json.get("concept", "AI Concept Failed")
            }
    except Exception as e:
        print(f"Error calling Gemini for question analysis: {e}")
        return {"topic": "AI Generation Failed", "skill": "AI Generation Failed", "area": "AI Generation Failed", "concept": "AI Generation Failed"}




# --- Helper function for synchronous Gemini API calls within tools ---
def call_gemini_sync_for_topic(question_text: str, api_key: str):
    """Makes a synchronous call to the Gemini API to generate a topic for a question."""
    if not api_key:
        return "Error: API Key Missing"

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    prompt = f"Analyze the following GMAT question and provide a concise topic for it (e.g., 'Rates & Ratios', 'Subject-Verb Agreement', 'Data Sufficiency - Geometry'). Return only the topic name. Question: \"{question_text}\""
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            # Extract text from the correct location in the Gemini API response
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"Error calling Gemini for topic generation: {e}")
        return "AI Topic Generation Failed"



@tool("get_performance_summary")
def get_performance_summary(db: Session, quiz_id: int = None, quiz_name: str = None):
    """
    Analyzes all performance records to provide a high-level summary.
    If quiz_id or quiz_name is provided, filters the summary for that specific quiz.
    If neither is provided, analyzes performance across all quizzes.
    """
    resolved_quiz_id = quiz_id
    if quiz_name and not quiz_id:
        resolved_quiz_id = resolve_quiz_identifier(db, quiz_name)
        if resolved_quiz_id is None:
            return json.dumps({"error": f"Quiz '{quiz_name}' not found."})
    
    query = db.query(PerformanceDB).options(joinedload(PerformanceDB.quiz))
    
    if resolved_quiz_id:
        query = query.filter(PerformanceDB.quiz_id == resolved_quiz_id)
        quiz_obj = db.query(QuizDB).filter(QuizDB.id == resolved_quiz_id).first()
        quiz_context = f"Quiz {resolved_quiz_id} ({quiz_obj.name})" if quiz_obj else f"Quiz {resolved_quiz_id}"
        quiz_info = {"id": quiz_obj.id, "name": quiz_obj.name, "timeLimitMinutes": quiz_obj.time_limit_minutes} if quiz_obj else None
    else:
        quiz_context = "All Quizzes"
        quiz_info = None
    
    records = query.all()
    if not records:
        return json.dumps({"message": f"No performance data found for {quiz_context.lower()}."})

    total_correct = sum(r.correct_answers for r in records)
    total_questions = sum(r.total_questions for r in records)
    overall_accuracy = f"{(total_correct / total_questions * 100):.1f}%" if total_questions > 0 else "N/A"
    
    performance_breakdown = parse_tool_result(call_tool("get_performance_by_question_type_and_difficulty", db, quiz_id=resolved_quiz_id))

    summary = {
        "context": quiz_context, "quizInfo": quiz_info, "totalAttempts": len(records),
        "overallAccuracy": overall_accuracy, "totalQuestionsAttempted": total_questions,
        "totalCorrectAnswers": total_correct, "performanceBreakdown": performance_breakdown.get("performanceBreakdown", [])
    }
    return json.dumps(summary, indent=2)

@tool("get_most_recent_incorrect_answers")
def get_most_recent_incorrect_answers(db: Session, quiz_id: int = None, quiz_name: str = None, limit: int = 5):
    """
    Retrieves details for the most recent questions the user answered incorrectly.
    """
    resolved_quiz_id = quiz_id
    if quiz_name and not quiz_id:
        resolved_quiz_id = resolve_quiz_identifier(db, quiz_name)
        if resolved_quiz_id is None:
            return json.dumps({"error": f"Quiz '{quiz_name}' not found."})
    
    query = db.query(PerformanceDB).order_by(PerformanceDB.timestamp.desc())
    if resolved_quiz_id:
        query = query.filter(PerformanceDB.quiz_id == resolved_quiz_id)
    
    latest_performance = query.first()
    if not latest_performance or not latest_performance.detailed_results_json:
        return json.dumps({"message": "No recent performance data with incorrect answers found."})
        
    detailed_results = json.loads(latest_performance.detailed_results_json)
    incorrect_answers = [q for q in detailed_results if not q.get('correct')]

    if not incorrect_answers:
        return json.dumps({"message": "No incorrect answers found in the most recent performance."})

    trimmed_results = []
    for q in incorrect_answers[:limit]:
        user_explanation = db.query(UserExplanationDB).filter(
            UserExplanationDB.performance_id == latest_performance.id,
            UserExplanationDB.question_id == q.get("questionId")
        ).first()
        trimmed_results.append({
            "questionId": q.get("questionId"), "questionText": q.get("questionText"),
            "userAnswer": q.get("userAnswer"), "correctAnswer": q.get("correctAnswer"),
            "answerExplanation": q.get("answerExplanation"), "question_type": q.get("question_type"),
            "difficulty": q.get("difficulty"), "userExplanation": user_explanation.explanation_text if user_explanation else None
        })

    quiz_info = None
    if latest_performance.quiz:
        quiz_info = {"id": latest_performance.quiz.id, "name": latest_performance.quiz.name}

    return json.dumps({
        "performanceId": latest_performance.id, "quizInfo": quiz_info,
        "incorrectAnswers": trimmed_results
    }, indent=2)

@tool("get_all_quizzes")
def get_all_quizzes(db: Session):
    """
    Retrieves all available quizzes with their basic information.
    """
    quizzes = db.query(QuizDB).all()
    if not quizzes:
        return json.dumps({"message": "No quizzes found."})
    
    quiz_data = []
    for quiz in quizzes:
        question_count = db.query(QuestionDB).filter(QuestionDB.quiz_id == quiz.id).count()
        quiz_data.append({
            "id": quiz.id, "name": quiz.name,
            "timeLimitMinutes": quiz.time_limit_minutes, "questionCount": question_count
        })
    return json.dumps({"quizzes": quiz_data}, indent=2)

@tool("get_quiz_questions")
def get_quiz_questions(db: Session, quiz_id: int, include_rc_passages: bool = True):
    """
    Retrieves questions for a specific quiz.
    """
    quiz = db.query(QuizDB).filter(QuizDB.id == quiz_id).first()
    if not quiz:
        return json.dumps({"message": f"Quiz with ID {quiz_id} not found."})
    
    query = db.query(QuestionDB).filter(QuestionDB.quiz_id == quiz_id)
    if include_rc_passages:
        query = query.options(joinedload(QuestionDB.rc_passage))
    
    questions = query.all()
    question_data = []
    for q in questions:
        q_info = {
            "id": q.id, "questionText": q.question_text, "options": json.loads(q.options_json or '{}'),
            "correctAnswer": q.correct_answer, "answerExplanation": q.answer_explanation,
            "difficulty": q.difficulty, "questionType": q.question_type
        }
        if q.rc_passage and include_rc_passages:
            q_info["rcPassage"] = {"id": q.rc_passage.id, "passage": q.rc_passage.passage_text}
        question_data.append(q_info)
        
    return json.dumps({"quizId": quiz_id, "quizName": quiz.name, "questions": question_data}, indent=2)

@tool("get_quizzes_sorted_by_date")
def get_quizzes_sorted_by_date(db: Session, ascending: bool = False, limit: int = None):
    """
    Retrieves all quiz performances sorted by the date they were taken.
    """
    query = db.query(PerformanceDB).options(joinedload(PerformanceDB.quiz))
    order = PerformanceDB.timestamp.asc() if ascending else PerformanceDB.timestamp.desc()
    query = query.order_by(order)
    if limit:
        query = query.limit(limit)
    
    performances = query.all()
    if not performances:
        return json.dumps({"message": "No quiz performances found."})
        
    quiz_data = []
    for perf in performances:
        quiz_data.append({
            "performanceId": perf.id, "quizId": perf.quiz_id,
            "quizName": perf.quiz.name if perf.quiz else "Unknown",
            "dateTaken": perf.timestamp.isoformat() if perf.timestamp else None,
            "accuracy": f"{(perf.correct_answers / perf.total_questions * 100):.1f}%" if perf.total_questions > 0 else "N/A"
        })
    return json.dumps({"quizzes": quiz_data}, indent=2)

@tool("get_most_recent_quiz_performance")
def get_most_recent_quiz_performance(db: Session):
    """
    Gets detailed performance data for the most recent quiz attempt.
    """
    return call_tool("analyze_latest_quiz_detailed", db)

@tool("get_performance_by_question_type_and_difficulty")
def get_performance_by_question_type_and_difficulty(db: Session, quiz_id: int = None):
    """
    Provides detailed performance breakdown by question type and difficulty level.
    """
    query = db.query(PerformanceDB)
    if quiz_id:
        query = query.filter(PerformanceDB.quiz_id == quiz_id)
    
    performances = query.all()
    if not performances:
        return json.dumps({"performanceBreakdown": []})
        
    breakdown = {}
    for perf in performances:
        if perf.detailed_results_json:
            detailed_results = json.loads(perf.detailed_results_json)
            for result in detailed_results:
                q_type = result.get('questionType', result.get('question_type', 'Unknown'))
                difficulty = result.get('difficulty', 'Unknown')
                key = (q_type, difficulty)
                if key not in breakdown:
                    breakdown[key] = {"total": 0, "correct": 0}
                breakdown[key]["total"] += 1
                if result.get('correct'):
                    breakdown[key]["correct"] += 1

    formatted_breakdown = {}
    for (q_type, difficulty), stats in breakdown.items():
        if q_type not in formatted_breakdown:
            formatted_breakdown[q_type] = {"overall": {"total": 0, "correct": 0}, "byDifficulty": {}}
        
        accuracy = f"{(stats['correct'] / stats['total'] * 100):.1f}%" if stats['total'] > 0 else "0.0%"
        formatted_breakdown[q_type]["byDifficulty"][difficulty] = {"total": stats["total"], "correct": stats["correct"], "accuracy": accuracy}
        formatted_breakdown[q_type]["overall"]["total"] += stats["total"]
        formatted_breakdown[q_type]["overall"]["correct"] += stats["correct"]

    for q_type in formatted_breakdown:
        overall_stats = formatted_breakdown[q_type]["overall"]
        overall_accuracy = f"{(overall_stats['correct'] / overall_stats['total'] * 100):.1f}%" if overall_stats['total'] > 0 else "0.0%"
        formatted_breakdown[q_type]["overall"]["accuracy"] = overall_accuracy

    return json.dumps({"performanceBreakdown": formatted_breakdown}, indent=2)

@tool("analyze_latest_quiz_detailed")
def analyze_latest_quiz_detailed(db: Session):
    """
    Provides comprehensive question-by-question analysis of the most recent quiz performance.
    """
    latest_performance = db.query(PerformanceDB).order_by(PerformanceDB.timestamp.desc()).first()
    if not latest_performance:
        return json.dumps({"message": "No quiz performances found."})
    return call_tool("analyze_performance_by_id", db, performance_id=latest_performance.id)
@tool("analyze_performance_by_id")
def analyze_performance_by_id(db: Session, performance_id: int):
    """
    Provides comprehensive details for ALL questions in a specific quiz performance.
    """
    performance = (db.query(PerformanceDB)
                   .options(joinedload(PerformanceDB.quiz))
                   .filter(PerformanceDB.id == performance_id)
                   .first())
    
    if not performance:
        return json.dumps({"error": f"Performance with ID {performance_id} not found."})

    if not performance.detailed_results_json:
        return json.dumps({"message": "No detailed results for this performance."})

    try:
        all_questions_details = json.loads(performance.detailed_results_json)
    except json.JSONDecodeError:
        return json.dumps({"error": f"Could not parse detailed results for performance ID {performance_id}."})
    
    for question_detail in all_questions_details:
        user_explanation = db.query(UserExplanationDB).filter(
            UserExplanationDB.performance_id == performance.id,
            UserExplanationDB.question_id == question_detail.get("questionId")
        ).first()
        question_detail["userExplanation"] = user_explanation.explanation_text if user_explanation else ""

    result = {
        "quizOverview": {
            "performanceId": performance.id,
            "quizName": performance.quiz.name if performance.quiz else "Unknown",
            "dateTaken": performance.timestamp.isoformat() if performance.timestamp else None,
        },
        "allAnswersDetails": all_questions_details
    }
    return json.dumps(result, indent=2)




@tool("create_error_log_csv")
def create_error_log_csv(db: Session, performance_id: int, gemini_api_key: str = None):
    """
    Creates CSV content of ALL questions for a specific quiz attempt,
    with AI-generated topics, skills, areas, and concepts, and returns it as a string.
    Uses an intelligent batching system to respect API rate limits.
    """
    api_key = gemini_api_key or os.environ.get("GOOGLE_API_KEY")

    analysis_result_str = call_tool("analyze_performance_by_id", db, performance_id=performance_id)
    analysis_result = parse_tool_result(analysis_result_str)

    if "error" in analysis_result or not analysis_result.get("allAnswersDetails"):
        return json.dumps({
            "status": "error", "message": "Could not generate error log.",
            "details": analysis_result.get("error", "No questions found in this attempt.")
        })

    all_answers = analysis_result["allAnswersDetails"]
    quiz_overview = analysis_result["quizOverview"]
    
    headers = [
        "Name", "Reviewed", "Section", "Topic", "Concept", "Complexity", "Root Cause",
        "Counter Measures", "Question Source", "Date", "Revisit Date",
        "Revisit Status", "Content Area", "Fundamental Skill", "Performance",
        "Time Spent (Minutes)"
    ]
    
    counters = {"Quant": 1, "Verbal": 1, "Data Insights": 1}

    try:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        # Process questions in batches to respect API rate limits (15 RPM)
        for i, question in enumerate(all_answers):
            section = question.get("question_type", "Unknown")
            
            name = "Unknown"
            if section in counters:
                name = f"{section[0]}{counters[section]}"
                counters[section] += 1

            # Generate topic, skill, area, and concept using AI
            ai_analysis = call_gemini_for_question_analysis(question.get("questionText", ""), api_key)

            date_taken_str = quiz_overview.get("dateTaken")
            date_formatted = ""
            if date_taken_str:
                try:
                    date_obj = datetime.fromisoformat(date_taken_str)
                    date_formatted = date_obj.strftime("%d/%m/%Y")
                except (ValueError, TypeError): date_formatted = date_taken_str

            time_spent_sec = question.get('timeSpent')
            time_spent_min = f"{time_spent_sec / 60:.2f}" if time_spent_sec is not None else ""

            row = {
                "Name": name,
                "Reviewed": False,
                "Section": section,
                "Topic": ai_analysis["topic"],
                "Concept": ai_analysis["concept"],
                "Complexity": question.get("difficulty", ""),
                "Root Cause": "",
                "Counter Measures": question.get("userExplanation", ""),
                "Question Source": quiz_overview.get("quizName", ""),
                "Date": date_formatted,
                "Revisit Date": "",
                "Revisit Status": False,
                "Content Area": ai_analysis["area"],
                "Fundamental Skill": ai_analysis["skill"],
                "Performance": "Correct" if question.get("correct") else "Incorrect",
                "Time Spent (Minutes)": time_spent_min
            }
            writer.writerow(row)
            
            # --- INTELLIGENT RATE LIMITING ---
            # After every 15th request, wait for 60 seconds to reset the minute quota.
            # We check `(i + 1)` because `i` is 0-indexed.
            # We also check if it's not the very last question to avoid an unnecessary wait.
            if (i + 1) % 15 == 0 and (i + 1) < len(all_answers):
                print(f"Processed batch of 15. Pausing for 60 seconds to respect API rate limit...")
                time.sleep(60)

        csv_content = output.getvalue()
        output.close()
        file_name = f"error_log_perf_{performance_id}.csv"

        return json.dumps({
            "status": "success", "message": "CSV content generated successfully.",
            "csv_content": csv_content, "file_name": file_name
        })

    except Exception as e:
        return json.dumps({"status": "error", "message": "An unexpected error occurred during CSV generation.", "errorDetails": str(e)})








AVAILABLE_TOOLS = _TOOL_REGISTRY

GEMINI_TOOLS = [
    {"name": "get_performance_summary", "description": "Get overall performance summary for a specific quiz or all quizzes.", "parameters": {"type": "object", "properties": {"quiz_id": {"type": "integer"}, "quiz_name": {"type": "string"}}}},
    {"name": "get_most_recent_incorrect_answers", "description": "Get details about recent incorrect answers.", "parameters": {"type": "object", "properties": {"quiz_id": {"type": "integer"}, "quiz_name": {"type": "string"}, "limit": {"type": "integer"}}}},
    {"name": "get_all_quizzes", "description": "Get a list of all available quizzes.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_quiz_questions", "description": "Get question information for a specific quiz.", "parameters": {"type": "object", "properties": {"quiz_id": {"type": "integer"}, "include_rc_passages": {"type": "boolean"}}, "required": ["quiz_id"]}},
    {"name": "get_quizzes_sorted_by_date", "description": "Get quiz performances sorted by date.", "parameters": {"type": "object", "properties": {"ascending": {"type": "boolean"}, "limit": {"type": "integer"}}}},
    {"name": "get_most_recent_quiz_performance", "description": "Get a comprehensive analysis of the most recent quiz attempt.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_performance_by_question_type_and_difficulty", "description": "Get performance breakdown by question type and difficulty.", "parameters": {"type": "object", "properties": {"quiz_id": {"type": "integer"}}}},
    {"name": "analyze_latest_quiz_detailed", "description": "Provides a detailed, question-by-question analysis of the most recent quiz performance.", "parameters": {"type": "object", "properties": {}}},
    {"name": "analyze_performance_by_id", "description": "Provides comprehensive analysis of a specific quiz performance by its ID.", "parameters": {"type": "object", "properties": {"performance_id": {"type": "integer"}}, "required": ["performance_id"]}},
    {"name": "create_error_log_csv", "description": "Creates a CSV error log for a specific quiz attempt.", "parameters": {"type": "object", "properties": {"performance_id": {"type": "integer"}}, "required": ["performance_id"]}}
]

unique_tools = []
seen_names = set()
for tool_def in GEMINI_TOOLS:
    if tool_def["name"] not in seen_names:
        unique_tools.append(tool_def)
        seen_names.add(tool_def["name"])
GEMINI_TOOLS = unique_tools

GEMINI_TOOL_CONFIG = {
    "function_calling_config": {
        "mode": "AUTO",
        "allowed_function_names": [tool['name'] for tool in GEMINI_TOOLS]
    }
}
