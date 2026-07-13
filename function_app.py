import azure.functions as func
import logging
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
import os
import json
import re
from urllib.parse import quote

# Matches AI Search / Azure OpenAI file-citation markers such as
# "【371:1†source】" (full-width brackets + dagger) and the ASCII fallbacks
# "[371:1+source]" / "[371:1†source]".
CITATION_TOKEN_RE = re.compile(r"[\[\u3010]\s*\d+:\d+\s*[\u2020\u2021+]\s*source\s*[\]\u3011]")

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="agent_httptrigger")
def agent_httptrigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    message = req.params.get('message')
    agentid = req.params.get('agentid')
    threadid = req.params.get('threadid')
    parameters = None
    
    if not message or not agentid:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = None

        if req_body:
            message = req_body.get('message')
            agentid = req_body.get('agentid')
            threadid = req_body.get('threadid')
            parameters = req_body.get('parameters')  # JSON object with name-value pairs

    if not message or not agentid:
        return func.HttpResponse(
            json.dumps({
                "error": "Missing required parameters 'message' and 'agentid'",
                "usage": "Provide 'message' and 'agentid' in query string or request body. Optional: 'threadid', 'parameters'"
            }),
            status_code=400,
            mimetype="application/json"
        )

    # Apply message template if configured
    # MESSAGE_TEMPLATE example: "user_id: {user_id}, username: {username}, question: {message}"
    message_template = os.environ.get("MESSAGE_TEMPLATE")
    if message_template:
        template_vars = {"message": message}
        if parameters and isinstance(parameters, dict):
            template_vars.update(parameters)
        try:
            message = message_template.format(**template_vars)
            logging.info(f"Applied message template with variables: {list(template_vars.keys())}")
        except KeyError as e:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Missing required parameter for message template: {str(e)}",
                    "provided_parameters": list(template_vars.keys()),
                    "template": message_template
                }),
                status_code=400,
                mimetype="application/json"
            )

    endpoint = os.environ.get("AIProjectEndpoint")
    
    if not endpoint:
        logging.error("AIProjectEndpoint must be set in environment variables.")
        return func.HttpResponse(
            "Internal Server Error: Missing AIProjectEndpoint configuration.",
            status_code=500
        )

    try:
        # Use endpoint-based authentication (SDK 2.0+)
        project_client = AIProjectClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )

        openai_client = project_client.get_openai_client()

        # agentid format: "name:version" or just "name"
        if ":" in agentid:
            agent_name, agent_version = agentid.split(":", 1)
        else:
            agent_name = agentid
            agent_version = None

        # Build agent reference
        agent_ref = {"name": agent_name, "type": "agent_reference"}
        if agent_version:
            agent_ref["version"] = agent_version

        # Create response using the OpenAI Responses API with agent reference
        create_kwargs = {
            "input": [{"role": "user", "content": message}],
            "extra_body": {"agent_reference": agent_ref},
        }
        if threadid:
            create_kwargs["previous_response_id"] = threadid

        response = openai_client.responses.create(**create_kwargs)

        # Optional base URL used to turn a stored file path/name into a clickable link
        # e.g. "https://<account>.blob.core.windows.net/<container>/"
        citation_base_url = os.environ.get("CITATION_BASE_URL", "").rstrip("/")

        def _attr(obj, *names):
            for name in names:
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

        # Collect unique sources (preserving first-seen order) and map each raw
        # citation token to a numbered reference like "[1]".
        sources = []          # list of (title, url_or_None)
        source_index = {}     # dedupe key -> reference number
        annotations_map = {}  # raw citation token -> "[n]"

        def _register_source(title, url):
            key = url or title
            if key in source_index:
                return source_index[key]
            number = len(sources) + 1
            source_index[key] = number
            sources.append((title, url))
            return number

        for item in response.output:
            if item.type == "message" and item.role == "assistant":
                for content_block in item.content:
                    if hasattr(content_block, "annotations") and content_block.annotations:
                        for ann in content_block.annotations:
                            # Log the raw annotation so we can confirm the shape AI Search returns
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
                                # ODF/AI Search grounding returns file citations without a URL.
                                # Build a clickable link from the public blob base URL + file name.
                                raw_name = _attr(ann, "filename", "title", "file_id") or "Source"
                                title = _friendly_title(raw_name)
                                url = _build_url(raw_name)
                                number = _register_source(title, url)
                            else:
                                continue

                            annotations_map[citation_text] = number

        # Renumber references in order of first appearance in the visible text so
        # the numbers read naturally (first citation shown is [1], etc.).
        assistant_text = response.output_text or ""
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

        # Fallback: replace any leftover raw markers (e.g. "【371:1†source】")
        # whose annotation spans didn't line up with the visible text.
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

        # Return the response with the thread ID for continuity
        response_data = {
            "message": assistant_text,
            "threadId": response.id
        }
        
        return func.HttpResponse(
            json.dumps(response_data, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
            charset="utf-8"
        )
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        # Include more detailed error information for debugging
        import traceback
        logging.error(traceback.format_exc())
        return func.HttpResponse(
            "Internal Server Error: " + str(e),
            status_code=500
        )
