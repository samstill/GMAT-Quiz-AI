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

# --- AI Helper Function with Retry Logic ---
def call_gemini_for_question_analysis(question_text: str, api_key: str, max_retries: int = 3):
    """
    Makes a synchronous call to the Gemini API with retry logic for rate limiting.
    Generates a topic, fundamental skill, content area, and in-depth concept for a question.
    """
    if not api_key:
        return {"topic": "Error: API Key Missing", "skill": "Error", "area": "Error", "concept": "Error"}

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
    
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(api_url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                response_text = result["candidates"][0]["content"]["parts"][0]["text"]
                clean_json_str = response_text.strip().replace('```json', '').replace('```', '').strip()
                
                analysis_json = json.loads(clean_json_str)
                
                return {
                    "topic": analysis_json.get("topic", "AI Topic Failed"),
                    "skill": analysis_json.get("skill", "AI Skill Failed"),
                    "area": analysis_json.get("area", "AI Area Failed"),
                    "concept": analysis_json.get("concept", "AI Concept Failed")
                }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                # Exponential backoff: wait 2, 4, 8 seconds
                wait_time = 2 ** (attempt + 1)
                print(f"Rate limited. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                print(f"Error calling Gemini for question analysis: {e}")
                return {"topic": "AI Generation Failed", "skill": "AI Generation Failed", "area": "AI Generation Failed", "concept": "AI Generation Failed"}
        except Exception as e:
            print(f"Error calling Gemini for question analysis: {e}")
            return {"topic": "AI Generation Failed", "skill": "AI Generation Failed", "area": "AI Generation Failed", "concept": "AI Generation Failed"}
    
    return {"topic": "AI Generation Failed after retries", "skill": "AI Generation Failed", "area": "AI Generation Failed", "concept": "AI Generation Failed"}

# (Your other tools like get_performance_summary, get_all_quizzes, etc. go here...)
# ...

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

        for question in all_answers:
            section = question.get("question_type", "Unknown")
            
            name = "Unknown"
            if section in counters:
                name = f"{section[0]}{counters[section]}"
                counters[section] += 1

            # Generate topic, skill, area, and concept using AI with retry logic
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
            
        csv_content = output.getvalue()
        output.close()
        file_name = f"error_log_perf_{performance_id}.csv"

        return json.dumps({
            "status": "success", "message": "CSV content generated successfully.",
            "csv_content": csv_content, "file_name": file_name
        })

    except Exception as e:
        return json.dumps({"status": "error", "message": "An unexpected error occurred during CSV generation.", "errorDetails": str(e)})

# (Your other tool definitions and GEMINI_TOOLS list go here)





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
