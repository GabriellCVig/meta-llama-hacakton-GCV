import uvicorn
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
from typing import Optional
from json import loads, JSONDecodeError
from transformers import pipeline

# llama_index + ollama
from llama_index.core.agent.workflow import (
    AgentWorkflow,
    ReActAgent
)
from llama_index.core.workflow import Context 
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama import Ollama

########################
# SETUP LOGGING
########################
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

########################
# HELPER LOGIC
########################
def assign_queue(severity: int) -> str:
    """
    Your existing queue assignment logic.
    """
    if severity <= 2:
        return "15 minutes"
    elif severity == 3:
        return "20 minutes"
    else:
        return "30 minutes"

def clean_llm_response(raw: str | object) -> str:
    """Enhanced cleaning function that handles both string and CompletionResponse objects"""
    if hasattr(raw, 'response'):  # Handle Ollama CompletionResponse
        cleaned = raw.response
    else:
        cleaned = str(raw)
        
    stops = ["<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>"]
    for s in stops:
        cleaned = cleaned.replace(s, "")
    return cleaned.strip()

# Summarization function
def summarize_symptoms_with_llm(new_info: str, previous_summary: str, llm: Ollama) -> str:
    if not previous_summary or previous_summary.isspace():
        previous_summary = ""
    
    prompt = f"""You are a medical symptom summarization assistant.
Role: Combine previous symptoms with new information into a concise medical summary.

Previous symptoms:
{previous_summary}

New symptom:
{new_info}

Rules:
1. Maintain the timing of when each symptom started or changed.
2. Eliminate duplicates.
3. Preserve timing details.
4. Use clinical terminology where appropriate.
5. Format the final output as bullet points (one line per symptom or important note), e.g.:
   * Fever and cough of recent onset
   * No preceding symptoms reported
6. If no previous symptoms, start fresh; if any exist, integrate seamlessly.

Return ONLY the bullet-pointed final summary (no extra text)."""
    
    logger.info("Sending prompt to LLM for symptom summarization.")
    response = llm.complete(prompt=prompt)
    cleaned_response = clean_llm_response(response)
    logger.info("Received summarized symptoms: %s", cleaned_response)
    return cleaned_response

# Triaging function
def run_esi_triage(summary: str, llm: Ollama) -> (int, str):
    logger.info("Running ESI triage with summary: %s", summary)
    try:
        with open("ESI_triage.md", "r") as f:
            esi_markdown = f.read()
    except Exception as e:
        esi_markdown = f"Error reading ESI guidelines: {e}"
        logger.error("Error reading ESI guidelines: %s", e)

    prompt = f"""You are an AI medical assistant trained on ESI Triage guidelines.

ESI Guidelines:
{esi_markdown}

Patient's summarized symptoms:
{summary}

Based on the guidelines above, provide valid JSON like:
{{
    "severity": <int>,
    "explanation": "<text>"
}}
ONLY respond with the JSON object containing the severity and explanation. Do NOT include anything else in your response.
No markdown formatting whatsoever. ONLY the {{…}} JSON object.
"""
    
    logger.info("Sending prompt to LLM for triage evaluation.")
    raw = llm.complete(prompt=prompt)
    cleaned = clean_llm_response(raw)
    try:
        data = loads(cleaned)
        severity = data.get("severity", -1)
        explanation = data.get("explanation", cleaned)
    except JSONDecodeError:
        severity = -1
        explanation = cleaned
        logger.error("Failed to parse JSON from LLM response. Raw response: %s", cleaned)

    logger.info("Triage evaluation complete. Severity: %d, Explanation: %s", severity, explanation)
    return severity, explanation


def translate_to_english(text: str, translator) -> str:
    """
    Uses the Hugging Face seamless-m4t-v2-large model to translate the provided text to English.
    """
    logger.info("Translating text to English using Hugging Face seamless-m4t-v2-large.")
    # Use "nob" as the source language for Norwegian Bokmål
    result = translator(text, src_lang="nob", tgt_lang="en")
    # The pipeline returns a list of dictionaries; we use the first translation result.
    translated_text = result[0]['translation_text']
    logger.info("Translation result: %s", translated_text)
    return translated_text


########################
# FASTAPI SETUP
########################
app = FastAPI(
    title="ER Triage w/ Ollama",
    description="Example multi-agent with local Ollama LLM",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# We'll create the LLM instance once here
ollama_llm = Ollama(
    model="llama3.3:70b-instruct-q8_0",
    request_timeout=120.0,
    # server_url="http://localhost:11411",  # specify if needed
)

## Instantiate Hugging Face translation pipeline using seamless-m4t-v2-large
#translator = pipeline("translation", model="facebook/seamless-m4t-v2-large")
translator = pipeline(
        "translation",
        model="./local_model_dir/models--facebook--seamless-m4t-v2-large/snapshots/5f8cc790b19fc3f67a61c105133b20b34e3dcb76/",
        use_fast=False  # Force use of slow tokenizer to avoid Tiktoken conversion issues.
        
    )
    
########################
# TOOLS
########################
async def SummarizeTool(ctx: Context, new_symptom: str) -> str:
    if new_symptom.lower().strip() == "confirm":
        logger.info("Received confirm command; skipping symptom update.")
        return await ctx.get("symptom_summary", default="")
    
    try:
        current_summary = await ctx.get("symptom_summary", default="")
        last_processed = await ctx.get("last_processed_symptom", default="")
        if new_symptom == last_processed:
            logger.info("Received duplicate symptom: '%s'", new_symptom)
            return current_summary
        logger.info("Processing new symptom. Current summary: '%s', New symptom: '%s'", current_summary, new_symptom)
        updated = summarize_symptoms_with_llm(new_symptom, current_summary, llm=ollama_llm)
        await ctx.set("symptom_summary", updated)
        await ctx.set("last_processed_symptom", new_symptom)
        logger.info("Updated summary stored: '%s'", updated)
        return updated
    except Exception as e:
        logger.error("Error in SummarizeTool: %s", str(e))
        return current_summary if current_summary else new_symptom

async def TriageTool(ctx: Context) -> dict:
    """
    Run ESI triage using the local LLM (ollama).
    """
    summary = await ctx.get("symptom_summary", default="")
    severity, explanation = run_esi_triage(summary, llm=ollama_llm)
    waitTime = assign_queue(severity)
    logger.info("Triage result: Severity=%d, WaitTime=%s", severity, waitTime)
    return {"severity": severity, "explanation": explanation, "waitTime": waitTime}

summarize_tool = FunctionTool.from_defaults(
    fn=SummarizeTool,
    name="SummarizeSymptomTool",
    description="Updates the symptom summary with new symptom text."
)

triage_tool = FunctionTool.from_defaults(
    fn=TriageTool,
    name="RunTriageTool",
    description="Evaluates the final summary via ESI guidelines."
)

########################
# AGENTS
########################
SymptomCollectorAgent = ReActAgent(
    name="SymptomCollectorAgent",
    description="Collects new symptom text from user. Then calls SummarizerAgent.",
    system_prompt="If user says 'confirm', done. Else hand symptom to SummarizerAgent.",
    llm=ollama_llm,   # <--- using Ollama
    tools=[],
    can_handoff_to=["SummarizerAgent"]
)

SummarizerAgent = ReActAgent(
    name="SummarizerAgent",
    description="Calls SummarizeSymptomTool to update symptom_summary.",
    system_prompt="You combine the new symptom with existing summary, returning updated summary.",
    llm=ollama_llm,
    tools=[summarize_tool],
    can_handoff_to=[]
)

TriageAgent = ReActAgent(
    name="TriageAgent",
    description="Evaluates the current symptom summary via ESI guidelines.",
    system_prompt="""You are the triage evaluator.
    Use the current 'symptom_summary' in the workflow context to perform a triage evaluation based on the ESI guidelines.
    Return ONLY a JSON object with keys "severity", "explanation", and "waitTime".
    Example: {"severity": 2, "explanation": "Patient needs immediate attention"}""",
    llm=ollama_llm,
    tools=[triage_tool],
    can_handoff_to=[]
)

ChatAgent = ReActAgent(
    name="ChatAgent",
    description="Root agent. If user says 'confirm', hand off to TriageAgent. Else SymptomCollectorAgent.",
    system_prompt="""If the user’s message is exactly "confirm", do not treat it as new symptom data. Instead, ignore any symptom‐updating actions and immediately hand off to the TriageAgent. The TriageAgent should use the current 'symptom_summary' in the workflow context to evaluate the patient according to the ESI guidelines and return a valid JSON with keys "severity", "explanation" and "waitTime".
For any other input, forward the message to the SymptomCollectorAgent to update the symptom summary.""",
    llm=ollama_llm,
    tools=[],
    can_handoff_to=["SymptomCollectorAgent", "TriageAgent"]
)

workflow = AgentWorkflow(
    agents=[ChatAgent, SymptomCollectorAgent, SummarizerAgent, TriageAgent],
    root_agent="ChatAgent",
    initial_state={"symptom_summary": ""},
    timeout=30
)

# We'll store sessions in memory
workflow_sessions = {}

########################
# DATA MODELS
########################
class ChatMessage(BaseModel):
    session_id: str
    message: str

class SessionResponse(BaseModel):
    session_id: str
    message: str

########################
# ENDPOINTS
########################
@app.post("/agent-workflow-start", response_model=SessionResponse)
async def agent_workflow_start():
    session_id = str(uuid.uuid4())
    # create new context
    ctx = Context(workflow=workflow)
    await ctx.set("symptom_summary", "")
    workflow_sessions[session_id] = ctx
    logger.info("Started new session with session_id: %s", session_id)
    return SessionResponse(session_id=session_id, message="Session started with local LLM. Please describe your symptoms.")

@app.post("/agent-workflow-chat")
async def agent_workflow_chat(chat: ChatMessage):
    session_id = chat.session_id
    if session_id not in workflow_sessions:
        logger.error("Session %s not found", session_id)
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    ctx = workflow_sessions[session_id]
    user_msg = chat.message.strip()
    logger.info("Received message from session %s: %s", session_id, user_msg)
    
    # Intercept the "confirm" message to trigger triage immediately.
    if user_msg.lower() == "confirm":
        triage_result = await TriageTool(ctx)
        logger.info("Triage result for session %s: %s", session_id, triage_result)
        return {"session_id": session_id, "message": str(triage_result)}
    
    handler = workflow.run(ctx=ctx, user_msg=user_msg)
    result = await handler
    logger.info("Workflow result for session %s: %s", session_id, result)
    
    translated_msg = translate_to_english(user_msg, translator)
    logger.info("Translated user message to English: %s", translated_msg)

    handler = workflow.run(ctx=ctx, user_msg=translated_msg)
    result = await handler
    logger.info("Workflow result for session %s: %s", session_id, result)
    return {"session_id": session_id, "message": str(result)}

@app.post("/agent-workflow-cleanup/{session_id}")
async def cleanup_session(session_id: str):
    if session_id in workflow_sessions:
        del workflow_sessions[session_id]
        logger.info("Cleaned up session: %s", session_id)
    else:
        logger.warning("Attempted to cleanup non-existent session: %s", session_id)
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info("Starting server on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)