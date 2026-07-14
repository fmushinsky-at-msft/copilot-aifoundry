import azure.functions as func
import logging
from agent_framework.azure import AzureAIClient
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.identity import DefaultAzureCredential
import os
import json
import asyncio
import re
from urllib.parse import quote
from pathlib import Path
from azure.ai.projects import AIProjectClient

# Matches AI Search / Azure OpenAI file-citation markers such as
# "【371:1†source】" (full-width brackets + dagger) and the ASCII fallbacks
# "[371:1+source]" / "[371:1†source]". Groups: 1 = doc index, 2 = chunk index.
CITATION_TOKEN_RE = re.compile(r"[\[\u3010]\s*(\d+):(\d+)\s*[\u2020\u2021+]\s*source\s*[\]\u3011]")

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
    logging.warning('TEMP-DIAG: Python HTTP trigger function processed a request.')

    message = req.params.get('message')
    agent_name = req.params.get('agent_name')
    instructions = req.params.get('instructions')
    threadid = req.params.get('threadid')
    parameters = None
    
    if not message:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = None

        if req_body:
            message = req_body.get('message')
            agent_name = req_body.get('agent_name')
            instructions = req_body.get('instructions')
            threadid = req_body.get('threadid')
            parameters = req_body.get('parameters')  # JSON object with name-value pairs

    if not message:
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
    model_deployment = os.environ.get("ModelDeploymentName", "gpt-4o-mini")
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
            # Continue existing conversation
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
            }
        )

        # --- Diagnostic: dump the full response so we can locate citation/source data ---
        try:
            if hasattr(response, "model_dump_json"):
                logging.warning(f"TEMP-DIAG RAW RESPONSE: {response.model_dump_json()}")
            elif hasattr(response, "to_json"):
                logging.warning(f"TEMP-DIAG RAW RESPONSE: {response.to_json()}")
            else:
                logging.warning(f"TEMP-DIAG RAW RESPONSE: {response}")
        except Exception as dump_err:
            logging.warning(f"Could not serialize response: {dump_err}")

        for _i, _item in enumerate(getattr(response, "output", []) or []):
            logging.warning(f"TEMP-DIAG Output[{_i}] type={getattr(_item, 'type', None)} "
                         f"role={getattr(_item, 'role', None)}")
        # --- End diagnostic ---

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

        def _collect_retrieved_sources():
            # When the agent doesn't return structured annotations, the source
            # documents are usually exposed via a file-search / tool-result output
            # item. Scan every output item defensively (objects OR dicts) for a
            # list of results carrying a file name / title / url.
            collected = []
            seen = set()
            for item in getattr(response, "output", []) or []:
                itype = (_attr(item, "type") or "")
                if not any(k in itype for k in ("file_search", "search", "tool", "retrieval")):
                    continue
                results = (_attr(item, "results", "output", "content", "documents") or [])
                if not isinstance(results, (list, tuple)):
                    continue
                for r in results:
                    name = _attr(r, "filename", "title", "file_id", "id", "name")
                    if not name:
                        continue
                    url = _attr(r, "url") or _build_url(name)
                    title = name if re.match(r"^https?://", name, re.IGNORECASE) else _friendly_title(name)
                    key = url or title
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append((title, url))
            return collected

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
                    logging.warning(
                        f"TEMP-DIAG Content block type={getattr(content_block, 'type', None)} "
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

                            if ann.type == "url_citation":
                                url = _attr(ann, "url")
                                title = _attr(ann, "title") or url or citation_text
                                number = _register_source(title, url)
                            elif ann.type == "file_citation":
                                raw_name = _attr(ann, "filename", "title", "file_id") or "Source"
                                title = _friendly_title(raw_name)
                                url = _build_url(raw_name)
                                number = _register_source(title, url)
                            else:
                                continue

                            annotations_map[citation_text] = number

        # Case 2: no (or partial) structured annotations. Resolve any inline
        # "【N:M†source】" tokens still present in the text using the retrieved
        # source documents from a file-search / tool-result output item.
        assistant_text = response.output_text or ""
        unresolved_tokens = [
            m.group(0)
            for m in CITATION_TOKEN_RE.finditer(assistant_text)
            if m.group(0) not in annotations_map
        ]
        if unresolved_tokens:
            retrieved = _collect_retrieved_sources()
            logging.warning(f"TEMP-DIAG Unresolved citation tokens={len(unresolved_tokens)} "
                         f"retrieved_sources={len(retrieved)}")
            if retrieved:
                unique_tokens = []
                for tok in unresolved_tokens:
                    if tok not in unique_tokens:
                        unique_tokens.append(tok)
                # Map by document index so multiple chunks of the same document
                # (e.g. "371:1" and "371:2") resolve to the same source.
                doc_to_source = {}
                seq = 0
                for tok in unique_tokens:
                    m = CITATION_TOKEN_RE.match(tok)
                    doc_idx = int(m.group(1)) if m else None
                    if doc_idx in doc_to_source:
                        title, url = doc_to_source[doc_idx]
                    elif doc_idx and 1 <= doc_idx <= len(retrieved):
                        # Token's doc index is a valid 1-based lookup.
                        title, url = retrieved[doc_idx - 1]
                        doc_to_source[doc_idx] = (title, url)
                    else:
                        # Out of range: fall back to citation order.
                        title, url = retrieved[seq % len(retrieved)]
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

        # Replace citations in the output text with numbered references.
        for token in ordered_tokens:
            new_number = old_to_new[annotations_map[token]]
            assistant_text = assistant_text.replace(token, f"[{new_number}]")

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

        result = {
        "message": assistant_text,
        "threadId": response.conversation.id
        }


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
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
