import azure.functions as func
import logging
from azure.identity import DefaultAzureCredential
import os
import json
import re
import time
import threading
import urllib.request
import urllib.error
from urllib.parse import quote
from azure.ai.projects import AIProjectClient

# ---------------------------------------------------------------------------
# Application Insights custom events
#
# Events are written to the App Insights "customEvents" table so usage can be
# queried and filtered with KQL. Requires APPLICATIONINSIGHTS_CONNECTION_STRING.
# If the exporter package is unavailable the calls degrade to structured logs
# (traces table) so telemetry never breaks the request.
# ---------------------------------------------------------------------------
_event_logger = None
_event_handler = None
_event_logger_ready = False
_event_logger_lock = threading.Lock()


def _get_event_logger():
    """Lazily build a logger that exports to the App Insights customEvents table."""
    global _event_logger, _event_handler, _event_logger_ready

    if _event_logger_ready:
        return _event_logger

    # Functions can run invocations concurrently in one worker; build once.
    with _event_logger_lock:
        if _event_logger_ready:
            return _event_logger

        conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if not conn:
            logging.warning("APPLICATIONINSIGHTS_CONNECTION_STRING not set; custom events go to traces only.")
            _event_logger_ready = True
            return None
        try:
            from opencensus.ext.azure.log_exporter import AzureEventHandler

            lg = logging.getLogger("agent_events")
            lg.setLevel(logging.INFO)
            lg.propagate = False
            if not lg.handlers:
                # Short export interval: Functions workers can be frozen shortly
                # after an invocation, so do not let events sit in the buffer.
                handler = AzureEventHandler(connection_string=conn, export_interval=2.0)
                lg.addHandler(handler)
                _event_handler = handler
            else:
                _event_handler = lg.handlers[0]
            _event_logger = lg
        except Exception as exporter_err:
            logging.warning(f"Custom event exporter unavailable ({exporter_err}); falling back to traces.")
            _event_logger = None
        finally:
            _event_logger_ready = True

    return _event_logger


def flush_events():
    """Force pending custom events to be sent.

    Azure Functions may freeze or recycle the worker as soon as a request
    completes, which would silently drop buffered telemetry. Call this before
    returning from a request. Never raises.
    """
    try:
        if _event_handler is not None:
            _event_handler.flush()
    except Exception as flush_err:
        logging.warning(f"flush_events failed: {flush_err}")


def _clean_dimensions(properties):
    """App Insights custom dimensions must be simple scalars; stringify safely."""
    cleaned = {}
    for key, value in (properties or {}).items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "true" if value else "false"
        elif isinstance(value, (int, float, str)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned


def track_event(name, properties=None, measurements=None):
    """Emit a custom event to App Insights and flush it. Never raises."""
    try:
        dims = _clean_dimensions(properties)
        if measurements:
            dims.update({k: v for k, v in measurements.items() if isinstance(v, (int, float))})

        lg = _get_event_logger()
        if lg is not None:
            lg.info(name, extra={"custom_dimensions": dims})
            # Flush immediately so the event survives worker freeze/recycle.
            flush_events()
        else:
            # Fallback: structured trace so the data is still queryable.
            logging.info(f"EVENT {name} {json.dumps(dims, ensure_ascii=False, default=str)}")
    except Exception as track_err:  # telemetry must never break the request
        logging.warning(f"track_event failed for '{name}': {track_err}")


def _truncate(text, limit=8000):
    """App Insights caps custom dimension values; keep them within range."""
    if text is None:
        return None
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def extract_token_usage(response):
    """Pull token counts out of a Responses API result.

    Returns a dict of numeric measurements suitable for App Insights. Shapes vary
    between API versions, so every field is probed defensively and missing values
    are simply omitted.
    """
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {}

    def _num(obj, *names):
        for name in names:
            value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
            if isinstance(value, (int, float)):
                return value
        return None

    metrics = {}
    # Responses API uses input/output; Chat Completions uses prompt/completion.
    input_tokens = _num(usage, "input_tokens", "prompt_tokens")
    output_tokens = _num(usage, "output_tokens", "completion_tokens")
    total_tokens = _num(usage, "total_tokens")

    if input_tokens is not None:
        metrics["inputTokens"] = input_tokens
    if output_tokens is not None:
        metrics["outputTokens"] = output_tokens
    if total_tokens is not None:
        metrics["totalTokens"] = total_tokens
    elif input_tokens is not None and output_tokens is not None:
        metrics["totalTokens"] = input_tokens + output_tokens

    # Reasoning models report the thinking tokens separately (billed as output).
    out_details = getattr(usage, "output_tokens_details", None)
    if out_details is None and isinstance(usage, dict):
        out_details = usage.get("output_tokens_details")
    if out_details is not None:
        reasoning = _num(out_details, "reasoning_tokens")
        if reasoning is not None:
            metrics["reasoningTokens"] = reasoning

    # Cached input tokens are billed at a lower rate; useful for cost analysis.
    in_details = getattr(usage, "input_tokens_details", None)
    if in_details is None and isinstance(usage, dict):
        in_details = usage.get("input_tokens_details")
    if in_details is not None:
        cached = _num(in_details, "cached_tokens")
        if cached is not None:
            metrics["cachedInputTokens"] = cached

    return metrics


# Basic email-address shape check for caller-supplied recipients.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# Matches AI Search / Azure OpenAI file-citation markers such as
# "【371:1†source】" (full-width brackets + dagger) and the ASCII fallbacks
# "[371:1+source]" / "[371:1†source]". Groups: 1 = doc index, 2 = chunk index.
CITATION_TOKEN_RE = re.compile(r"[\[\u3010]\s*(\d+):(\d+)\s*[\u2020\u2021+]\s*source\s*[\]\u3011]")

# Phrases that indicate the agent could not answer from its knowledge base.
# Used to set a "canAnswer" flag so the Copilot Studio topic can offer to
# email the question to HR. Configurable via NO_ANSWER_MARKERS (";"-separated).
DEFAULT_NO_ANSWER_MARKERS = [
    "cannot answer this question based on the Benefit Open Enrollment information",
    "i cannot answer this question",
    "apologies, but i cannot answer",
    "NO_ANSWER",
]


def detect_no_answer(text):
    """Return True if the assistant text signals it could not answer."""
    if not text:
        return True
    raw = os.environ.get("NO_ANSWER_MARKERS", "")
    markers = [m.strip() for m in raw.split(";") if m.strip()] or DEFAULT_NO_ANSWER_MARKERS
    lowered = text.lower()
    return any(m.lower() in lowered for m in markers)


def summarize_conversation(openai_client, conversation_id, model):
    """Best-effort summary of a conversation's prior turns, used to carry a
    little context forward when we roll over to a fresh conversation. Returns a
    short plain-text summary, or None on any failure."""
    try:
        items = openai_client.conversations.items.list(conversation_id=conversation_id)

        # Collect only user/assistant message text, skipping bulky tool outputs.
        transcript = []
        for it in items:
            role = getattr(it, "role", None) or (it.get("role") if isinstance(it, dict) else None)
            if role not in ("user", "assistant"):
                continue
            content = getattr(it, "content", None) or (it.get("content") if isinstance(it, dict) else None)
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, (list, tuple)):
                for block in content:
                    btext = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
                    if btext:
                        text += btext
            if text.strip():
                transcript.append(f"{role}: {text.strip()}")

        if not transcript:
            return None

        # Cap the transcript size we send to the summarizer to avoid re-hitting
        # the context window while summarizing.
        joined = "\n".join(transcript)[-6000:]

        summary_resp = openai_client.responses.create(
            model=model,
            input=[
                {"type": "message", "role": "system", "content": (
                    "Summarize the following assistant/user conversation in 3-5 concise "
                    "bullet points. Capture key facts, decisions, and unresolved questions "
                    "so the assistant can continue seamlessly. Do not add new information."
                )},
                {"type": "message", "role": "user", "content": joined},
            ],
        )
        summary = (getattr(summary_resp, "output_text", "") or "").strip()
        return summary or None
    except Exception as sum_err:
        logging.warning(f"Conversation summarization failed: {sum_err}")
        return None


def render_message_with_citations(response):
    """Convert an agent response into a message with human-readable, clickable
    citations and a Sources list. Isolated so a failure here can degrade to the
    raw answer instead of breaking the whole request."""
    # Optional base URL used to turn a stored file path/name into a clickable link
    # e.g. "https://<account>.blob.core.windows.net/<container>/"
    citation_base_url = os.environ.get("CITATION_BASE_URL", "").rstrip("/")

    def _attr(obj, *names):
        for name in names:
            if isinstance(obj, dict):
                value = obj.get(name)
            else:
                value = getattr(obj, name, None)
            if value:
                return value
        return None

    def _friendly_title(name):
        # Turn a blob file name into a nicer display label:
        # "terminal_ops-manual.odt" -> "Terminal Ops Manual"
        label = name.rsplit("/", 1)[-1]
        label = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", label)  # drop extension
        label = re.sub(r"[_\-]+", " ", label).strip()
        return label.title() if label else name

    def _build_url(name):
        if not name:
            return None
        # Already an absolute URL? Use as-is.
        if re.match(r"^https?://", name, re.IGNORECASE):
            return name
        if not citation_base_url:
            return None
        # URL-encode each path segment so spaces/special chars don't break the link.
        encoded = "/".join(quote(part) for part in name.split("/") if part)
        return f"{citation_base_url}/{encoded}"

    def _decode_search_filename(doc_id):
        # Azure AI Search doc ids look like:
        #   "file-Additional_Info_2026_pdf-<HEX>-page-2"
        # where <HEX> is the hex-encoded original filename
        # (e.g. "Additional Info 2026.pdf"). Prefer decoding the hex
        # segment; fall back to the human-ish prefix.
        if not doc_id:
            return None
        m = re.search(r"-([0-9A-Fa-f]{16,})-", doc_id)
        if m:
            try:
                decoded = bytes.fromhex(m.group(1)).decode("utf-8", errors="strict")
                if decoded.strip():
                    return decoded
            except (ValueError, UnicodeDecodeError):
                pass
        # Fallback: strip "file-" prefix and the hex/page suffix.
        name = re.sub(r"^file-", "", doc_id)
        name = re.sub(r"-[0-9A-Fa-f]{16,}.*$", "", name)
        return name or None

    def _search_documents():
        # Parse the "azure_ai_search_call_output" items. Their `output` is a
        # JSON string containing a "documents" list. Returns an ordered list
        # of (title, url) — the index matches the model's "doc_N" citations.
        docs = []
        for item in getattr(response, "output", []) or []:
            itype = (_attr(item, "type") or "")
            if "search" not in itype:
                continue
            raw = _attr(item, "output")
            if not raw:
                continue
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            for d in data.get("documents") or []:
                # filepath/title are usually empty; derive from the id.
                name = _attr(d, "filepath", "title") or _decode_search_filename(_attr(d, "id"))
                if not name:
                    continue
                title = _friendly_title(name)
                url = _build_url(name)  # link into the public blob container
                docs.append((title, url))
        return docs

    # Parse the AI Search result documents once (index == model's "doc_N").
    search_docs = _search_documents()
    logging.info(f"Parsed search documents: {len(search_docs)}")

    # Collect unique sources (preserving first-seen order) and map each raw
    # citation token to a numbered reference like "[1]".
    sources = []          # list of (title, url_or_None)
    source_index = {}     # dedupe key -> reference number
    annotations_map = {}  # raw citation token -> reference number

    def _register_source(title, url):
        key = url or title
        if key in source_index:
            return source_index[key]
        number = len(sources) + 1
        source_index[key] = number
        sources.append((title, url))
        return number

    # Case 1: structured annotations returned by the model/grounding layer.
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) == "message" and getattr(item, "role", None) == "assistant":
            for content_block in getattr(item, "content", []) or []:
                ann_count = len(getattr(content_block, "annotations", None) or [])
                logging.info(
                    f"Content block type={getattr(content_block, 'type', None)} "
                    f"annotations={ann_count}"
                )
                if hasattr(content_block, "annotations") and content_block.annotations:
                    for ann in content_block.annotations:
                        logging.info(f"Annotation: {ann}")

                        if ann.start_index is None or ann.end_index is None:
                            continue
                        citation_text = content_block.text[ann.start_index:ann.end_index]
                        if not citation_text:
                            continue

                        title = None
                        url = None
                        if ann.type == "url_citation":
                            ann_title = _attr(ann, "title") or ""
                            ann_url = _attr(ann, "url")
                            # AI Search returns title="doc_N" (an index into
                            # the search documents) with a generic search
                            # endpoint URL. Resolve it to the real document.
                            m_doc = re.match(r"^doc_(\d+)$", ann_title)
                            if m_doc and search_docs:
                                idx = int(m_doc.group(1))
                                if 0 <= idx < len(search_docs):
                                    title, url = search_docs[idx]
                            if title is None:
                                title = ann_title or ann_url or citation_text
                                url = ann_url
                        elif ann.type == "file_citation":
                            raw_name = _attr(ann, "filename", "title", "file_id") or "Source"
                            title = _friendly_title(raw_name)
                            url = _build_url(raw_name)
                        else:
                            continue

                        annotations_map[citation_text] = _register_source(title, url)

    # Case 2: any inline "【N:M†source】" tokens still present in the text that
    # weren't covered by an annotation span. Resolve them against the parsed
    # search documents (the leading number is a 1-based document index).
    assistant_text = response.output_text or ""
    unresolved_tokens = [
        m.group(0)
        for m in CITATION_TOKEN_RE.finditer(assistant_text)
        if m.group(0) not in annotations_map
    ]
    if unresolved_tokens:
        logging.info(f"Unresolved citation tokens={len(unresolved_tokens)} "
                     f"search_documents={len(search_docs)}")
        if search_docs:
            unique_tokens = []
            for tok in unresolved_tokens:
                if tok not in unique_tokens:
                    unique_tokens.append(tok)
            # Map by document index so multiple chunks of the same document
            # (e.g. "3:1" and "3:2") resolve to the same source.
            doc_to_source = {}
            seq = 0
            for tok in unique_tokens:
                m = CITATION_TOKEN_RE.match(tok)
                doc_idx = int(m.group(1)) if m else None
                if doc_idx in doc_to_source:
                    title, url = doc_to_source[doc_idx]
                elif doc_idx and 1 <= doc_idx <= len(search_docs):
                    # Token's doc index is a valid 1-based lookup.
                    title, url = search_docs[doc_idx - 1]
                    doc_to_source[doc_idx] = (title, url)
                else:
                    # Out of range: fall back to citation order.
                    title, url = search_docs[seq % len(search_docs)]
                    doc_to_source[doc_idx] = (title, url)
                    seq += 1
                annotations_map[tok] = _register_source(title, url)

    # Renumber references in order of first appearance in the visible text so
    # the numbers read naturally (first citation shown is [1], etc.).
    ordered_tokens = sorted(
        annotations_map,
        key=lambda tok: (assistant_text.find(tok) if tok in assistant_text else len(assistant_text)),
    )
    old_to_new = {}
    renumbered_sources = []
    for token in ordered_tokens:
        old_number = annotations_map[token]
        if old_number not in old_to_new:
            old_to_new[old_number] = len(renumbered_sources) + 1
            renumbered_sources.append(sources[old_number - 1])
    sources = renumbered_sources

    # Replace citations in the output text with numbered references. Insert a
    # separating space when the marker would attach to a non-space character
    # (otherwise a preceding URL auto-link would swallow the "[n]").
    def _insert_ref(text, token, ref):
        out = []
        i = 0
        while True:
            j = text.find(token, i)
            if j == -1:
                out.append(text[i:])
                break
            prev = text[j - 1] if j > 0 else ""
            sep = "" if (prev == "" or prev.isspace()) else " "
            out.append(text[i:j])
            out.append(sep + ref)
            i = j + len(token)
        return "".join(out)

    for token in ordered_tokens:
        new_number = old_to_new[annotations_map[token]]
        assistant_text = _insert_ref(assistant_text, token, f"[{new_number}]")

    # Strip any leftover raw markers whose spans/sources couldn't be resolved.
    assistant_text = CITATION_TOKEN_RE.sub("", assistant_text)

    # Append a clickable Sources list.
    if sources:
        lines = ["", "", "**Sources:**"]
        for i, (title, url) in enumerate(sources, start=1):
            if url:
                lines.append(f"{i}. [{title}]({url})")
            else:
                lines.append(f"{i}. {title}")
        assistant_text += "\n".join(lines)

    if not assistant_text:
        assistant_text = "No assistant message found."

    return assistant_text


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="agent_httptrigger")
def agent_httptrigger(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger function that creates and interacts with AI Foundry agents using the 
    Microsoft Foundry Agent Framework SDK (agent-framework-azure-ai).
    
    Parameters (query string or JSON body):
        - message: User message to send to the agent (required)
        - agent_name: Name of the agent to create (optional, defaults to 'AssistantAgent')
        - instructions: Custom instructions for the agent (optional)
        - threadid: Existing thread ID for conversation continuity (optional)
        - parameters: JSON object with name-value pairs for instruction template substitution (optional)
    
    Environment Variables:
        - AGENT_INSTRUCTIONS_TEMPLATE: Template string with {variable} placeholders (optional)
          Example: "You are an HR assistant. User: {user_name} (ID: {user_id})"
        - PERSIST_AGENT: Set to 'true' to persist agents by name
        - AGENT_ID: Specific agent ID to use (overrides PERSIST_AGENT)
    """
    logging.info('Python HTTP trigger function processed a request.')
    _started = time.time()

    message = req.params.get('message')
    agent_name = req.params.get('agent_name')
    instructions = req.params.get('instructions')
    threadid = req.params.get('threadid')
    parameters = None
    
    if not message:
        req_body = None
        try:
            req_body = req.get_json()
        except ValueError:
            # Malformed JSON body — most commonly caused by an unescaped double
            # quote in the user's question breaking the caller's JSON payload.
            raw = ""
            try:
                raw = req.get_body().decode("utf-8", errors="replace")
            except Exception:
                pass
            logging.warning(
                "Request JSON parse failed (likely unescaped characters in the body). "
                "Set DEBUG_RAW_RESPONSE=true to log the raw payload."
            )
            if os.environ.get("DEBUG_RAW_RESPONSE", "").lower() in ("1", "true", "yes"):
                logging.warning(f"Raw body (truncated): {raw[:1000]}")
            # Lenient re-parse attempt: try to recover common escaping problems
            # (bare newlines/tabs and unescaped inner double quotes).
            if raw:
                try:
                    req_body = json.loads(raw)
                except Exception:
                    try:
                        repaired = raw.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
                        req_body = json.loads(repaired)
                        logging.info("Recovered request body after lenient re-parse.")
                    except Exception as reparse_err:
                        logging.warning(f"Lenient re-parse also failed: {reparse_err}")
                        req_body = None

        if req_body:
            message = req_body.get('message')
            agent_name = req_body.get('agent_name')
            instructions = req_body.get('instructions')
            threadid = req_body.get('threadid')
            parameters = req_body.get('parameters')  # JSON object with name-value pairs

    if not message:
        logging.warning("Returning 400: no usable 'message' in query params or request body.")
        return func.HttpResponse(
            json.dumps({
                "error": "Missing required parameter 'message'",
                "usage": "Provide 'message' in query string or request body. Optional: 'agent_name', 'instructions', 'threadid'"
            }),
            status_code=400,
            mimetype="application/json"
        )

    # Set defaults
    agent_name = agent_name or "AssistantAgent"
    
    # Handle instruction templates from environment variables
    instruction_template = os.environ.get("AGENT_INSTRUCTIONS_TEMPLATE")
    if instruction_template and parameters:
        # Use template with variable substitution
        try:
            instructions = instruction_template.format(**parameters)
            logging.info(f"Applied instruction template with parameters: {list(parameters.keys())}")
        except KeyError as e:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Missing required parameter for instruction template: {str(e)}",
                    "template_variables": list(parameters.keys()) if parameters else []
                }),
                status_code=400,
                mimetype="application/json"
            )
        except (IndexError, ValueError) as e:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Invalid AGENT_INSTRUCTIONS_TEMPLATE configuration: {str(e)}"
                }),
                status_code=500,
                mimetype="application/json"
            )
    else:
        # Use provided instructions or default
        instructions = instructions or "You are a helpful assistant."
    
    endpoint = os.environ.get("AIProjectEndpoint")
    model_deployment = os.environ.get("ModelDeploymentName", "gpt-5.5")
    agent_id = os.environ.get("AGENT_ID")  # Optional: use existing agent instead of creating ephemeral ones
    
    # If no AGENT_ID in env but agent_name is provided in request with PERSIST_AGENT=true,
    # the function will find/create agent by that name
    
    if not endpoint:
        logging.error("AIProjectEndpoint must be set in environment variables.")
        return func.HttpResponse(
            json.dumps({"error": "Server configuration error: Missing AIProjectEndpoint"}),
            status_code=500,
            mimetype="application/json"
        )

    try:
        # Run the async agent interaction
        project_client = AIProjectClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )

        # Get an existing agent
        agent = project_client.agents.get(agent_name=agent_id)

        # Get the OpenAI client for responses
        openai_client = project_client.get_openai_client()

        if threadid:
            # Continue existing conversation, but cap history so the accumulated
            # messages + large tool outputs never exceed the model context window.
            # MAX_CONVERSATION_TURNS: number of user turns to keep before rolling
            # over to a fresh conversation (default 8; set 0 to disable the cap).
            try:
                max_turns = int(os.environ.get("MAX_CONVERSATION_TURNS", "8"))
            except ValueError:
                max_turns = 8

            rollover = False
            if max_turns > 0:
                try:
                    existing_items = openai_client.conversations.items.list(
                        conversation_id=threadid
                    )
                    user_turns = sum(
                        1 for it in existing_items
                        if getattr(it, "role", None) == "user"
                        or (isinstance(it, dict) and it.get("role") == "user")
                    )
                    logging.info(f"Conversation {threadid} user turns={user_turns} (cap={max_turns})")
                    if user_turns >= max_turns:
                        rollover = True
                except Exception as list_err:
                    # If we can't inspect history, roll over to be safe rather
                    # than risk another context_length_exceeded failure.
                    logging.warning(f"Could not list conversation items, rolling over: {list_err}")
                    rollover = True

            if rollover:
                logging.info(f"Conversation {threadid} exceeded turn cap; starting a fresh conversation.")
                # Optional: carry a short summary of the prior conversation into
                # the fresh one so follow-up questions retain some context.
                # Enabled by default; disable with ENABLE_SUMMARY_CARRYOVER=false.
                seed_items = [{"type": "message", "role": "system", "content": instructions}]
                if os.environ.get("ENABLE_SUMMARY_CARRYOVER", "true").lower() not in ("0", "false", "no"):
                    summary = summarize_conversation(openai_client, threadid, model_deployment)
                    if summary:
                        logging.info("Carrying conversation summary into new conversation.")
                        seed_items.append({
                            "type": "message",
                            "role": "system",
                            "content": f"Summary of the earlier conversation for context:\n{summary}",
                        })
                seed_items.append({"type": "message", "role": "user", "content": message})
                conversation = openai_client.conversations.create(items=seed_items)
                conversation_id = conversation.id
            else:
                conversation_id = threadid
                # get the conversation to ensure it exists
                conversation = openai_client.conversations.retrieve(conversation_id)

                # Add the new user message to the existing conversation
                openai_client.conversations.items.create(
                    conversation_id=conversation_id,
                    items=[{"type": "message", "role": "user", "content": message}]
                )

        else:
            # Create a conversation for context persistence
            conversation = openai_client.conversations.create(
                items=[{"type": "message", "role": "system", "content": instructions},
                    {"type": "message", "role": "user", "content": message}],
            )

            conversation_id = conversation.id
        
        response = openai_client.responses.create(
            conversation=conversation_id,
            input="",  # Empty since we already added the message to the conversation
            extra_body={
                "agent": {"type": "agent_reference", "name": agent.name},
            },
        )

        # --- Diagnostic: dump the full response so we can locate citation/source data.
        # OFF by default: the raw response contains the employee's HR profile and
        # full knowledge-base document text, which should not be persisted in
        # telemetry. Enable temporarily with DEBUG_RAW_RESPONSE=true. ---
        if os.environ.get("DEBUG_RAW_RESPONSE", "").lower() in ("1", "true", "yes"):
            try:
                if hasattr(response, "model_dump_json"):
                    logging.info(f"RAW RESPONSE: {response.model_dump_json()}")
                elif hasattr(response, "to_json"):
                    logging.info(f"RAW RESPONSE: {response.to_json()}")
                else:
                    logging.info(f"RAW RESPONSE: {response}")
            except Exception as dump_err:
                logging.warning(f"Could not serialize response: {dump_err}")

        # Structure-only diagnostics (no content) are always safe to log.
        for _i, _item in enumerate(getattr(response, "output", []) or []):
            logging.info(f"Output[{_i}] type={getattr(_item, 'type', None)} "
                         f"role={getattr(_item, 'role', None)}")
        # --- End diagnostic ---

        # Post-process citations into clickable, numbered references. This must
        # never break the actual answer, so any failure degrades to raw text.
        try:
            assistant_text = render_message_with_citations(response)
        except Exception as cit_err:
            logging.error(f"Citation post-processing failed: {cit_err}")
            import traceback
            logging.error(traceback.format_exc())
            assistant_text = (getattr(response, "output_text", "") or "").strip() or "No assistant message found."

        # Flag whether the agent could answer, so the Copilot Studio topic can
        # offer to email the question to HR when it could not. Detect first (the
        # NO_ANSWER sentinel may be present), then strip the sentinel so it is
        # never shown to the user.
        can_answer = not detect_no_answer(assistant_text)
        logging.info(f"canAnswer={can_answer}")

        # Remove the NO_ANSWER sentinel (and tidy leftover whitespace) from the
        # user-visible message.
        assistant_text = re.sub(r"\s*NO_ANSWER\s*", " ", assistant_text).strip()
        if not assistant_text:
            assistant_text = "No assistant message found."

        result = {
        "message": assistant_text,
        "threadId": response.conversation.id,
        "canAnswer": can_answer
        }

        # --- Telemetry: one event per interaction. The canAnswer dimension
        # distinguishes answered from unanswered questions. Question text is only
        # captured when the agent could NOT answer, so it can be reviewed later.
        # Agent replies are never captured. ---
        _elapsed_ms = int((time.time() - _started) * 1000)
        _params = parameters if isinstance(parameters, dict) else {}
        _props = {
            "agentName": agent_name,
            "conversationId": response.conversation.id,
            "userId": _params.get("user_id"),
            "userName": _params.get("user_full_name"),
            "canAnswer": can_answer,
            "isNewConversation": not threadid,
        }
        if not can_answer:
            _props["question"] = _truncate(message)

        # Token usage reported by the model for this turn (input/output/total,
        # plus reasoning and cached-input counts when the model provides them).
        _measurements = {"durationMs": _elapsed_ms}
        _usage = extract_token_usage(response)
        _measurements.update(_usage)
        if _usage:
            logging.info(f"Token usage: {_usage}")
        else:
            logging.info("Token usage not reported by the API for this response.")

        track_event(
            "AgentInteraction",
            properties=_props,
            measurements=_measurements,
        )

        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
            charset="utf-8"
        )
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        track_event(
            "AgentInteractionFailed",
            properties={
                "agentName": agent_name,
                "question": _truncate(message),
                "error": _truncate(str(e), 2000),
            },
            measurements={"durationMs": int((time.time() - _started) * 1000)},
        )
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="send_hr_email")
def send_hr_email(req: func.HttpRequest) -> func.HttpResponse:
    """Send a user's unanswered question to HR via Microsoft Graph, using the
    Function's managed identity.

    Request (query string or JSON body):
        - question (required): the user's question to forward
        - user_email (required): the employee's email; the message is sent from this
          mailbox so HR sees it as coming directly from them
        - to_address (required): destination mailbox for the question
        - user_full_name (optional): who is asking
        - user_id (optional): employee id
        - conversation_id (optional): for traceability

    Environment variables:
        - HR_ALLOWED_RECIPIENTS (optional): comma/semicolon separated allow-list of
          addresses or domains that 'to_address' may target. Strongly recommended,
          otherwise any caller with the function key can pick any recipient.
    """
    logging.info("send_hr_email trigger invoked.")

    # --- Parse inputs (query params first, then JSON body) ---
    question = req.params.get("question")
    user_full_name = req.params.get("user_full_name")
    user_id = req.params.get("user_id")
    user_email = req.params.get("user_email")
    to_address = req.params.get("to_address")
    conversation_id = req.params.get("conversation_id")

    if not question:
        body = None
        try:
            body = req.get_json()
        except ValueError:
            # Not valid JSON — log the raw payload so the caller's shape is visible.
            raw = ""
            try:
                raw = req.get_body().decode("utf-8", errors="replace")
            except Exception:
                pass
            logging.warning("send_hr_email: JSON parse failed. Set DEBUG_RAW_RESPONSE=true to log the raw payload.")
            if os.environ.get("DEBUG_RAW_RESPONSE", "").lower() in ("1", "true", "yes"):
                logging.warning(f"send_hr_email raw body (truncated): {raw[:1000]}")
            if raw:
                try:
                    body = json.loads(raw)
                except Exception:
                    body = None

        # Some callers (certain Power Automate connectors) send the JSON payload
        # double-encoded as a string. Decode one extra level if needed.
        if isinstance(body, (str, bytes)):
            try:
                body = json.loads(body)
                logging.info("send_hr_email: decoded double-encoded JSON body.")
            except Exception:
                logging.warning("send_hr_email: body was a string but not valid JSON.")
                body = None

        if isinstance(body, dict):
            question = body.get("question")
            user_full_name = body.get("user_full_name")
            user_id = body.get("user_id")
            user_email = body.get("user_email")
            to_address = body.get("to_address")
            conversation_id = body.get("conversation_id")
        elif body is not None:
            logging.warning(f"send_hr_email: unexpected body type {type(body).__name__}.")

    if not question:
        logging.warning("send_hr_email: returning 400 - no 'question' in query params or body.")
        return func.HttpResponse(
            json.dumps({"error": "Missing required parameter 'question'"}),
            status_code=400,
            mimetype="application/json",
        )

    if not user_email:
        logging.warning("send_hr_email: returning 400 - no 'user_email' supplied.")
        return func.HttpResponse(
            json.dumps({"error": "Missing required parameter 'user_email'"}),
            status_code=400,
            mimetype="application/json",
        )

    to_addr = (to_address or "").strip()
    if not to_addr:
        logging.warning("send_hr_email: returning 400 - no 'to_address' supplied.")
        return func.HttpResponse(
            json.dumps({"error": "Missing required parameter 'to_address'"}),
            status_code=400,
            mimetype="application/json",
        )

    # Basic shape check so malformed input fails fast rather than at Graph.
    if not EMAIL_RE.match(to_addr):
        logging.warning("send_hr_email: returning 400 - 'to_address' is not a valid email address.")
        return func.HttpResponse(
            json.dumps({"error": "Parameter 'to_address' is not a valid email address"}),
            status_code=400,
            mimetype="application/json",
        )

    # Optional allow-list. Because the recipient now comes from the request, this
    # prevents the endpoint being used to mail arbitrary addresses. Entries may be
    # full addresses ("hr@panynj.gov") or domains ("@panynj.gov" / "panynj.gov").
    allowed_raw = os.environ.get("HR_ALLOWED_RECIPIENTS", "").strip()
    if allowed_raw:
        allowed = [a.strip().lower().lstrip("@") for a in re.split(r"[;,]", allowed_raw) if a.strip()]
        target = to_addr.lower()
        target_domain = target.split("@", 1)[-1]
        if target not in allowed and target_domain not in allowed:
            logging.warning(f"send_hr_email: recipient '{to_addr}' is not in HR_ALLOWED_RECIPIENTS.")
            return func.HttpResponse(
                json.dumps({"error": "Recipient address is not permitted"}),
                status_code=403,
                mimetype="application/json",
            )
    else:
        logging.warning(
            "HR_ALLOWED_RECIPIENTS is not set; 'to_address' is unrestricted. "
            "Set it to limit which recipients this endpoint may email."
        )

    try:
        # --- Acquire a Microsoft Graph token via the managed identity ---
        credential = DefaultAzureCredential()
        token = credential.get_token("https://graph.microsoft.com/.default").token

        # --- Build the message ---
        who = user_full_name or "An employee"
        who_line = f"{who}" + (f" (ID: {user_id})" if user_id else "")
        body_lines = [
            "A user question could not be answered by the Benefits assistant and was forwarded for help.",
            "",
            f"From: {who_line}",
            f"Email: {user_email}",
        ]
        if conversation_id:
            body_lines.append(f"Conversation: {conversation_id}")
        body_lines += ["", "Question:", question]
        email_text = "\n".join(body_lines)

        message = {
            "subject": "Benefits question forwarded from the assistant",
            "body": {"contentType": "Text", "content": email_text},
            "toRecipients": [{"emailAddress": {"address": to_addr}}],
        }

        # The email is always sent from the employee's own mailbox, so HR sees the
        # request coming directly from them and replies land in their inbox.
        # This requires the managed identity's Mail.Send application permission to
        # cover employee mailboxes (see the Exchange Application Access Policy).
        sender_mailbox = user_email

        graph_payload = {
            "message": message,
            "saveToSentItems": True,
        }

        # --- Send via Graph sendMail ---
        url = f"https://graph.microsoft.com/v1.0/users/{quote(sender_mailbox)}/sendMail"
        data = json.dumps(graph_payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as resp:
            status = resp.status  # 202 Accepted on success

        logging.info(f"HR email sent (status {status}) to {to_addr} as {sender_mailbox}.")
        track_event(
            "EmailSent",
            properties={
                "question": _truncate(question),
                "userEmail": user_email,
                "userId": user_id,
                "userName": user_full_name,
                "conversationId": conversation_id,
                "hrAddress": to_addr,
                "graphStatus": status,
            },
        )
        return func.HttpResponse(
            json.dumps({"sent": True, "message": "Your question has been emailed to HR."}),
            status_code=200,
            mimetype="application/json",
        )
    except urllib.error.HTTPError as http_err:
        detail = ""
        try:
            detail = http_err.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        logging.error(f"Graph sendMail failed: {http_err.code} {detail}")
        track_event(
            "EmailFailed",
            properties={
                "question": _truncate(question),
                "userEmail": user_email,
                "userId": user_id,
                "conversationId": conversation_id,
                "hrAddress": to_addr,
                "errorCode": http_err.code,
                "error": _truncate(detail, 2000),
            },
        )
        return func.HttpResponse(
            json.dumps({"sent": False, "error": f"Graph error {http_err.code}", "detail": detail}),
            status_code=502,
            mimetype="application/json",
        )
    except Exception as e:
        logging.error(f"send_hr_email error: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        track_event(
            "EmailFailed",
            properties={
                "question": _truncate(question),
                "userEmail": user_email,
                "userId": user_id,
                "conversationId": conversation_id,
                "error": _truncate(str(e), 2000),
            },
        )
        return func.HttpResponse(
            json.dumps({"sent": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
