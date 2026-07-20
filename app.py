import os
import io
import base64
import uuid
import json
import threading
import webbrowser
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify, session, Response
from werkzeug.utils import secure_filename

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import PyPDF2
from groq import Groq
from medical_kb import retrieve_guidelines

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "doctor-time-saver-secret-key")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")
MAX_HISTORY_ITEMS = 50


def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(entry: dict) -> None:
    try:
        history = load_history()
        history.insert(0, entry)
        history = history[:MAX_HISTORY_ITEMS]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def summarize_for_history(analysis_text: str, max_len: int = 90) -> str:
    for line in analysis_text.splitlines():
        clean = line.strip().lstrip("#").lstrip("-").strip()
        clean = clean.replace("*", "").strip()
        if len(clean) > 3:
            return clean[:max_len] + ("…" if len(clean) > max_len else "")
    return "Analysis result"


def clean_analysis_text(text: str) -> str:
    if not text:
        return text
    import re
    
    # Remove any introductory conversational text and summary headings at the start
    text = re.sub(
        r"^(?:Based on the|This is an|I have analyzed|Here is).*?(?:(?:\*\*\*|---|___)+|(?:###|##|#)+)\s*(?:Summary|Interpretation|Detailed|📋|📄).*?(?:Report|Findings|Results|Analysis)(?: Findings)?\s*\n*",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    # Split text by horizontal rules to remove trailing disclaimer block
    parts = re.split(r'\n*(?:\*\*\*|---|___)\n*', text)
    if len(parts) > 1:
        last_part = parts[-1].strip()
        disclaimer_keywords = ["ai", "doctor", "physician", "medical advice", "diagnosis", "disclaimer", "not a medical", "clinical correlation"]
        lower_last = last_part.lower()
        if any(kw in lower_last for kw in disclaimer_keywords) and (
            lower_last.startswith("disclaimer") or 
            lower_last.startswith("**disclaimer") or
            lower_last.startswith("###") or
            lower_last.startswith("##") or
            lower_last.startswith("#") or
            lower_last.startswith("⚠️") or
            lower_last.startswith("🚨") or
            lower_last.startswith("🛑") or
            lower_last.startswith("important") or
            lower_last.startswith("note") or
            lower_last.startswith("**note") or
            lower_last.startswith("warning") or
            lower_last.startswith("reminder") or
            lower_last.startswith("caveat") or
            "i am an ai" in lower_last or
            "not replace a consultation" in lower_last or
            "cannot replace a consultation" in lower_last
        ):
            text = "***".join(parts[:-1]).strip()
            
    # Remove any other remaining disclaimer headings/paragraphs at the end
    text = re.sub(
        r"\n*(?:\*\*\*|---|___)?\s*(?:###|##|#)?\s*(?:\*\*)?(?:⚠️|🚨|🛑)?\s*(?:Important\s+)?Disclaimer(?:\*\*)?(?::)?\s*.*$",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    text = re.sub(
        r"\n*(?:\*\*\*|---|___)?\s*(?:###|##|#)?\s*(?:\*\*)?(?:⚠️|🚨|🛑)?\s*Important\s+(?:Disclaimer|Note|Reminder|Warning|Caveats|Medical Disclaimer)(?:\*\*)?(?::)?\s*.*$",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    text = re.sub(
        r"\n*(?:\*\*\*|---|___)?\s*Please remember that\s*(?:\*\*)?I am an AI assistant\s*not a medical doctor.*$",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(r"\n*(?:\*\*\*|---|___)\s*$", "", text)
    return text.strip()



GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
try:
    ai_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except Exception:
    ai_client = None

MODEL_NAME = "llama-3.1-8b-instant"


def is_ollama_available() -> bool:
    global ai_client
    if not ai_client:
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            pass
        key = os.environ.get("GROQ_API_KEY")
        if key:
            try:
                ai_client = Groq(api_key=key)
            except Exception:
                pass
    return ai_client is not None


def model_supports_vision() -> bool:
    return False


SYSTEM_PROMPT = """AI Lab Report Interpreter" - a general medical report analysis assistant.

You must read the medical report text/image and interpret it.
Your job is to:
1. Start your response DIRECTLY with the test analysis. Do NOT include any conversational introduction, greetings, headers, or introductory paragraphs. Jump straight to the list of parameters.
2. Go through EACH test/parameter mentioned in the report. For each one, clearly state the value, the normal reference range, and whether it is ✅ Normal, ⚠️ Low, or 🔴 High.
   Format each parameter exactly like this:
   - **Test Name**: [Your Value] (Reference Range: [Range]) — [Status Symbol] [Normal / Low / High]
     *Note: [Brief 1-sentence explanation of what it means (only include this note for abnormal values to keep generation fast)]*
3. Mention possible diagnoses or patterns suggested by the overall results (e.g. "this pattern can be seen in...") ONLY if strongly supported.
4. Keep the output extremely short, clear, and direct. Do NOT include any extra details, general health tips, unsolicited advice, or conversational filler.
5. If the report has multiple sections or pages, summarize all of them.

Style Rules:
- Respond in plain, simple English.
- Use emojis for clarity (✅ ⚠️ 🔴).
- Use headings and bullet points for readability.
- Do NOT use math blocks, LaTeX formatting, or dollar signs ($). Write all measurements in plain text.
- Do not assume the report is about any specific disease unless the actual values in front of you support that.
- Start directly with the bulleted list of parameters. No intro or outro text whatsoever.
"""


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pil_image(img: Image.Image) -> str:
    global ai_client
    if not ai_client:
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            pass
        key = os.environ.get("GROQ_API_KEY")
        if key:
            try:
                ai_client = Groq(api_key=key)
            except Exception:
                pass
    if not ai_client:
        return "[OCR ERROR: Tesseract OCR binary is missing on the server, and Groq API key is not configured for remote vision extraction.]"

    try:
        # Convert transparent / RGBA / LA images to RGB with white background
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            alpha_composite = Image.alpha_composite(background, img)
            img = alpha_composite.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize image if it exceeds the maximum pixel limit of Groq Vision API
        # Groq allows max 33177600 pixels. We use a conservative limit of 20000000 pixels (20 MP).
        MAX_PIXELS = 20000000
        width, height = img.size
        total_pixels = width * height
        if total_pixels > MAX_PIXELS:
            scale_factor = (MAX_PIXELS / total_pixels) ** 0.5
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.LANCZOS
            img = img.resize((new_width, new_height), resample_filter)

        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        response = ai_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please transcribe all readable text, values, parameters, and reference ranges from this medical lab report image. Output only the transcribed text. Do not add any conversational text, explanation, warnings, or formatting wrappers."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.0
        )
        text = response.choices[0].message.content or ""
        return text.strip()
    except Exception as e:
        return f"[OCR ERROR: Failed to extract text via vision model: {str(e)}]"


def extract_text_from_image(image_path: str) -> str:
    import shutil
    has_tesseract = shutil.which("tesseract") is not None
    if has_tesseract:
        try:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang="eng", timeout=20)
            return text.strip()
        except Exception:
            pass
            
    try:
        img = Image.open(image_path)
        return extract_text_from_pil_image(img)
    except Exception as e:
        return f"[OCR ERROR: {e}]"


def extract_text_from_pdf(pdf_path: str) -> str:
    extracted_text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    if len(reader.pages) > 1:
                        extracted_text += f"\n--- Page {i+1} ---\n"
                    extracted_text += page_text
        if extracted_text.strip():
            return extracted_text.strip()
    except Exception:
        pass

    # If PyPDF2 couldn't extract text, check if we can do OCR on the server
    import shutil
    has_tesseract = shutil.which("tesseract") is not None
    has_pdftoppm = shutil.which("pdftoppm") is not None
    
    if not has_pdftoppm:
        return "[ERROR: The PDF has no selectable text, and server-side PDF-to-image conversion tools are not installed. Please upload your document as an image file (PNG/JPG) instead.]"

    try:
        pages = convert_from_path(pdf_path, 150)
        for i, page in enumerate(pages):
            if has_tesseract:
                try:
                    text = pytesseract.image_to_string(page, lang="eng", timeout=20)
                except Exception:
                    text = extract_text_from_pil_image(page)
            else:
                text = extract_text_from_pil_image(page)
                
            if len(pages) > 1:
                extracted_text += f"\n--- Page {i+1} ---\n"
            extracted_text += text
        return extracted_text.strip()
    except Exception as e:
        return f"[PDF OCR ERROR: {e}]"


@app.route("/")
def index():
    history = load_history()
    return render_template("index.html", history=history)


@app.route("/health")
def health():
    available = is_ollama_available()
    supports_vision = model_supports_vision()
    return jsonify({
        "ollama_available": available,
        "model": MODEL_NAME,
        "vision_supported": supports_vision
    })


@app.route("/history")
def history():
    raw_history = load_history()
    normalized_history = []
    for item in raw_history:
        analysis = clean_analysis_text(item.get("analysis", ""))
        title = clean_analysis_text(item.get("title") or item.get("summary") or summarize_for_history(analysis))
        source_name = item.get("source_name") or item.get("filename") or "Pasted text"
        timestamp_display = item.get("timestamp_display") or item.get("timestamp") or ""
        timestamp = item.get("timestamp") or timestamp_display or ""
        
        normalized_history.append({
            "id": item.get("id"),
            "title": title,
            "source_name": source_name,
            "question": item.get("question", ""),
            "analysis": analysis,
            "extracted_text": item.get("extracted_text", ""),
            "timestamp": timestamp,
            "timestamp_display": timestamp_display
        })
    return jsonify({"history": normalized_history})


@app.route("/history/<item_id>", methods=["DELETE"])
def delete_history_item(item_id):
    try:
        raw_history = load_history()
        new_history = [item for item in raw_history if item.get("id") != item_id]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(new_history, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/analyze", methods=["POST"])
def analyze():
    question = request.form.get("question", "").strip()
    
    extracted_text = ""
    filename = ""
    img_base64 = None
    ext = ""
    filepath = ""
    
    if "file" in request.files:
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            
            ext = filename.rsplit(".", 1)[1].lower()
            
            if ext in ["png", "jpg", "jpeg"]:
                if model_supports_vision():
                    try:
                        with open(filepath, "rb") as f:
                            img_base64 = base64.b64encode(f.read()).decode("utf-8")
                    except Exception as e:
                        return jsonify({"success": False, "error": f"Failed to read image: {str(e)}"}), 500
                else:
                    extracted_text = extract_text_from_image(filepath)
            elif ext == "pdf":
                extracted_text = extract_text_from_pdf(filepath)
        else:
            return jsonify({"success": False, "error": "Invalid file type"}), 400
    elif "report_text" in request.form:
        extracted_text = request.form.get("report_text", "").strip()
        filename = ""
    else:
        return jsonify({"success": False, "error": "No file or text provided"}), 400
        
    if extracted_text:
        if extracted_text.startswith("[ERROR:") or extracted_text.startswith("[OCR ERROR:") or extracted_text.startswith("[PDF OCR ERROR:"):
            error_msg = extracted_text.strip("[]")
            if "tesseract not found" in error_msg.lower() or "tesseract is not installed" in error_msg.lower():
                error_msg = "Tesseract OCR binary is missing on the server. Please install Tesseract or upload your document as an image file (PNG/JPG)."
            return jsonify({"success": False, "error": error_msg}), 400

    def generate_stream():
        yield json.dumps({"event": "extracted_text", "text": extracted_text}) + "\n"
        
        global ai_client
        if not ai_client:
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
            except ImportError:
                pass
            key = os.environ.get("GROQ_API_KEY")
            if key:
                try:
                    ai_client = Groq(api_key=key)
                except Exception:
                    pass

        if not ai_client:
            yield json.dumps({"event": "error", "error": "Groq API key is not set. Please set the GROQ_API_KEY environment variable."}) + "\n"
            return

        analysis = ""
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
            
            prompt = f"Report Text Content:\n{extracted_text}"
            if question:
                prompt += f"\n\nFocus especially on this question from the user: {question}"
            messages.append({"role": "user", "content": prompt})

            response_stream = ai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.0,
                stream=True
            )

            for chunk in response_stream:
                token = chunk.choices[0].delta.content or ""
                analysis += token
                yield json.dumps({"event": "token", "text": token}) + "\n"
                
        except Exception as e:
            yield json.dumps({"event": "error", "error": f"Groq error: {str(e)}"}) + "\n"
            return

        analysis = clean_analysis_text(analysis)
        
        timestamp_raw = datetime.now().isoformat()
        timestamp_disp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_name = filename if filename else "Pasted text"
        title = summarize_for_history(analysis)
        
        new_id = str(uuid.uuid4())
        history_entry = {
            "id": new_id,
            "title": title,
            "source_name": source_name,
            "question": question,
            "analysis": analysis,
            "extracted_text": extracted_text,
            "timestamp": timestamp_raw,
            "timestamp_display": timestamp_disp
        }
        
        save_history(history_entry)
        
        yield json.dumps({
            "event": "done",
            "history_id": new_id,
            "timestamp": timestamp_disp,
            "analysis": analysis
        }) + "\n"

    return Response(generate_stream(), mimetype="application/x-ndjson")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        data = request.json or {}
        question = data.get("question", "").strip()
        report_text = data.get("report_text", "").strip()
        analysis = data.get("analysis", "").strip()
        history = data.get("history", [])

        if not question:
            return jsonify({"success": False, "error": "No question provided"}), 400

        # Retrieve relevant clinical guidelines using RAG
        retrieved = retrieve_guidelines(question, report_text or analysis)
        
        # Format the retrieved guidelines into a context block
        guidelines_context = ""
        retrieved_meta = []
        for g in retrieved:
            guidelines_context += f"### {g['title']}\n{g['content']}\n\n"
            retrieved_meta.append({
                "id": g["id"],
                "title": g["title"]
            })

        # Base prompt for the LLM
        system_prompt = f"""You are "AI Patient Assistant", a precise and highly accurate assistant.
Your role is to answer the patient's specific question regarding their lab report directly, concisely, and with maximum accuracy.

Retrieved guidelines for context:
{guidelines_context or "No specific guidelines."}

Patient's Lab Report Text:
{report_text or "No report text."}

Initial Report Analysis:
{analysis or "No initial analysis."}

Instructions:
1. Answer the patient's question directly, clearly, and concisely: "{question}"
2. Ground your answer strictly and ONLY on the provided Lab Report Text, Initial Report Analysis, and the retrieved Guidelines. Do NOT assume, extrapolate, speculate, or introduce any external information.
3. If the user's message is a greeting, thank you, or polite remark, reply politely and directly in a single brief sentence (e.g., "You're welcome! Let me know if you have any other questions.").
4. Otherwise, start directly with the answer. Do NOT include greetings, conversational filler, introductory remarks, or small talk.
5. Only address the specific question asked. Do not provide extra details, general warnings, unrelated guidance, or unsolicited lifestyle advice unless it directly answers the question.
6. Keep the response as brief as possible, using short direct bullet points or simple sentences.
7. Do NOT use LaTeX, math blocks, or dollar signs.
8. Do NOT append long disclaimer blocks or warning paragraphs at the end. Keep it to a single brief sentence if absolutely necessary, or omit entirely.
"""

        # Construct messages list for Ollama
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Append conversation history
        for msg in history:
            messages.append({
                "role": msg.get("role"),
                "content": msg.get("content")
            })
            
        # Append current user question
        messages.append({"role": "user", "content": question})

        def chat_stream():
            reply = ""
            global ai_client
            if not ai_client:
                try:
                    from dotenv import load_dotenv
                    load_dotenv(override=True)
                except ImportError:
                    pass
                key = os.environ.get("GROQ_API_KEY")
                if key:
                    try:
                        ai_client = Groq(api_key=key)
                    except Exception:
                        pass

            if not ai_client:
                yield json.dumps({"event": "error", "error": "Groq API key is not set. Please set the GROQ_API_KEY environment variable."}) + "\n"
                return

            try:
                response_stream = ai_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.0,
                    stream=True
                )
                for chunk in response_stream:
                    token = chunk.choices[0].delta.content or ""
                    reply += token
                    yield json.dumps({"event": "token", "text": token}) + "\n"
            except Exception as e:
                yield json.dumps({"event": "error", "error": f"Failed to get response: {str(e)}"}) + "\n"
                return

            reply = clean_analysis_text(reply)
            yield json.dumps({
                "event": "done",
                "response": reply,
                "retrieved_guidelines": retrieved_meta
            }) + "\n"

        return Response(chat_stream(), mimetype="application/x-ndjson")

    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to get response: {str(e)}"}), 500


def open_browser(port):
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()


if __name__ == '__main__':
    # Render provides a $PORT environment variable. If it doesn't exist, default to 5002.
    port = int(os.environ.get("PORT", 5002))
    # Only open browser if running locally (PORT not defined in env)
    if "PORT" not in os.environ:
        open_browser(port)
    # You must bind to 0.0.0.0 so Render can route traffic to it
    app.run(host='0.0.0.0', port=port, debug=False)
