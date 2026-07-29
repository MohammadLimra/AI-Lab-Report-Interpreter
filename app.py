import os
import io
import base64
import uuid
import json
import threading
import webbrowser
import random
import re
import requests
from datetime import datetime
from functools import wraps

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for
from werkzeug.utils import secure_filename

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import PyPDF2
from groq import Groq
from medical_kb import retrieve_guidelines

from database import (
    init_db,
    create_user,
    get_user_by_email,
    save_otp,
    verify_otp,
    verify_otp_status,
    get_active_otp,
    extend_otp_expiry,
    load_history_for_user,
    save_history_for_user,
    delete_history_item_for_user,
    migrate_guest_history
)

from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "doctor-time-saver-secret-key")
CORS(app)

OTP_CONFIG = {
    "otp_length": 6,
    "expires_in": 300,                 
    "allowed_attempts": 3,             
    "resend_strategy": "reuse",        
    "store_otp_method": "encrypt"      
}

init_db()

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.before_request
def ensure_session_id():
    if "user_id" not in session and "guest_id" not in session:
        session["guest_id"] = f"guest_{uuid.uuid4()}"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/") or request.path in ["/history", "/analyze"]:
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("auth_page"))
        return f(*args, **kwargs)
    return decorated_function


def send_otp_email(recipient_email, otp_code):
    brevo_api_key = os.getenv("BREVO_API_KEY")
    if not brevo_api_key:
        return False, False, "BREVO_API_KEY is not set in environment (.env)"

    sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@example.com")
    sender_name = os.getenv("BREVO_SENDER_NAME", "AI Report Interpreter")
    
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": brevo_api_key,
        "content-type": "application/json"
    }
    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email
        },
        "to": [
            {
                "email": recipient_email
            }
        ],
        "subject": "Your Verification Code",
        "htmlContent": f"<p>Your verification code is: <strong>{otp_code}</strong></p>"
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code in (200, 201, 202):
            print(f"Email sent successfully via Brevo API! Status: {res.status_code}")
            return True, False, None
        else:
            err_msg = f"Brevo API error (status {res.status_code}): {res.text}"
            print(err_msg)
            return False, False, err_msg
    except Exception as e:
        print(f"Brevo API exception caught: {e}")
        return False, False, str(e)


def send_report_email(recipient_email, report_title, report_analysis):
    brevo_api_key = os.getenv("BREVO_API_KEY")
    if not brevo_api_key or not recipient_email:
        return False, "BREVO_API_KEY or recipient email missing"

    sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@example.com")
    sender_name = os.getenv("BREVO_SENDER_NAME", "AI Report Interpreter")
    
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": brevo_api_key,
        "content-type": "application/json"
    }
    
    html_analysis = report_analysis.replace("\n", "<br>")
    
    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email
        },
        "to": [
            {
                "email": recipient_email
            }
        ],
        "subject": f"Medical Lab Report Summary: {report_title}",
        "htmlContent": f"""
        <div style="font-family: sans-serif; max-width: 650px; margin: 0 auto; padding: 24px; background: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
            <h2 style="color: #4f46e5; margin-top: 0;">AI Medical Lab Report Summary</h2>
            <p style="font-size: 14px; color: #4b5563;"><strong>Title:</strong> {report_title}</p>
            <div style="background: #f9fafb; padding: 16px; border-radius: 8px; font-size: 14px; line-height: 1.7; color: #1f2937;">
                {html_analysis}
            </div>
            <p style="font-size: 12px; color: #9ca3af; margin-top: 20px; text-align: center;">Stored securely in your AI Lab Report Interpreter account ({recipient_email}).</p>
        </div>
        """
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code in (200, 201, 202):
            print(f"Report emailed successfully to {recipient_email}! Status: {res.status_code}")
            return True, None
        else:
            err_msg = f"Brevo API error (status {res.status_code}): {res.text}"
            print(err_msg)
            return False, err_msg
    except Exception as e:
        print(f"Brevo API exception caught: {e}")
        return False, str(e)


def load_history() -> list:
    identifier = session.get("user_id") or session.get("guest_id")
    if not identifier:
        return []
    return load_history_for_user(identifier)


def save_history(entry: dict, identifier: str = None) -> None:
    if not identifier:
        try:
            identifier = session.get("user_id") or session.get("guest_id")
        except RuntimeError:
            return
    if not identifier:
        return
    save_history_for_user(identifier, entry)


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
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY"))


def model_supports_vision() -> bool:
    return True


def generate_stream_llm(prompt, system_prompt=None, messages_history=None, img_base64=None):
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass

    gemini_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")

    if not gemini_key and not groq_key:
        yield "[ERROR: No AI API key found. Please set GEMINI_API_KEY or GROQ_API_KEY in .env]"
        return

    if gemini_key:
        contents = []
        if messages_history:
            for msg in messages_history:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        
        user_parts = [{"text": prompt}]
        if img_base64:
            user_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_base64}})
            
        contents.append({"role": "user", "parts": user_parts})
        
        payload = {"contents": contents}
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}

        candidate_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.0-flash-lite"]
        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={gemini_key}"
            try:
                res = requests.post(url, json=payload, stream=True, timeout=30)
                if res.status_code == 200:
                    for line in res.iter_lines():
                        if line:
                            decoded = line.decode("utf-8")
                            if decoded.startswith("data: "):
                                try:
                                    data = json.loads(decoded[6:])
                                    candidates = data.get("candidates", [])
                                    if candidates and "content" in candidates[0]:
                                        parts = candidates[0]["content"].get("parts", [])
                                        for part in parts:
                                            if "text" in part:
                                                yield part["text"]
                                except Exception:
                                    pass
                    return
                elif res.status_code == 429:
                    continue
            except Exception as e:
                print(f"Gemini API exception for model {model_name}: {e}")
                continue

    if groq_key:
        global ai_client
        if not ai_client:
            try:
                ai_client = Groq(api_key=groq_key)
            except Exception as e:
                yield f"[Groq client init error: {str(e)}]"
                return
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if messages_history:
                for msg in messages_history:
                    messages.append({"role": msg.get("role"), "content": msg.get("content")})
            
            if img_base64:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]
                })
            else:
                messages.append({"role": "user", "content": prompt})

            response_stream = ai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.0,
                stream=True
            )
            for chunk in response_stream:
                token = chunk.choices[0].delta.content or ""
                yield token
            return
        except Exception as e:
            yield f"[Groq API error: {str(e)}]"
            return

    yield "[ERROR: Could not connect to AI service. Please verify your GEMINI_API_KEY or GROQ_API_KEY in .env]"



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
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGBA")
                background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                alpha_composite = Image.alpha_composite(background, img)
                img = alpha_composite.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            for vision_model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{vision_model}:generateContent?key={gemini_key}"
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": "Please transcribe all readable text, values, parameters, and reference ranges from this medical lab report image. Output only the transcribed text. Do not add any conversational text, explanation, warnings, or formatting wrappers."},
                                {"inline_data": {"mime_type": "image/jpeg", "data": img_base64}}
                            ]
                        }
                    ]
                }
                res = requests.post(url, json=payload, timeout=30)
                if res.status_code == 200:
                    text = res.json()["candidates"][0]["content"]["parts"][0].get("text", "").strip()
                    if text:
                        return text
        except Exception as e:
            print(f"Gemini Vision API error: {e}")

    global ai_client
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key and not ai_client:
        try:
            ai_client = Groq(api_key=groq_key)
        except Exception:
            pass

    if ai_client:
        try:
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGBA")
                background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                alpha_composite = Image.alpha_composite(background, img)
                img = alpha_composite.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

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
            
            vision_models = []
            custom_model = os.environ.get("GROQ_VISION_MODEL") or os.environ.get("VISION_MODEL")
            if custom_model:
                vision_models.append(custom_model)
            for candidate in ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]:
                if candidate not in vision_models:
                    vision_models.append(candidate)

            last_error = None
            for vision_model in vision_models:
                try:
                    response = ai_client.chat.completions.create(
                        model=vision_model,
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
                    if text.strip():
                        return text.strip()
                except Exception as model_err:
                    last_error = str(model_err)
                    continue
        except Exception as e:
            print(f"Groq vision error: {e}")

    return "[OCR ERROR: Tesseract OCR binary is missing on the server, and remote Vision API extraction failed. Please check your GEMINI_API_KEY or GROQ_API_KEY in .env.]"


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


@app.route("/auth")
def auth_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    return render_template("auth.html", google_client_id=google_client_id)


@app.route("/api/auth/logout")
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/api/auth/send-otp", methods=["POST"])
def send_otp():
    data = request.json or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400
        
    if "@" not in email:
        email += "@gmail.com"
        
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return jsonify({"success": False, "error": "Invalid email address"}), 400
        
    otp_code = None
    resend_strat = OTP_CONFIG.get("resend_strategy", "rotate")
    store_method = OTP_CONFIG.get("store_otp_method", "plain")
    secret_key = app.secret_key
    
    if resend_strat == "reuse" and store_method != "hash":
        active_otp_rec = get_active_otp(email)
        if active_otp_rec:
            if active_otp_rec.get("attempts", 0) < OTP_CONFIG.get("allowed_attempts", 3):
                stored_otp_val = active_otp_rec["otp"]
                try:
                    if store_method == "encrypt":
                        from database import decrypt_otp
                        otp_code = decrypt_otp(stored_otp_val, secret_key)
                    else:
                        otp_code = stored_otp_val
                    extend_otp_expiry(email, expires_in_seconds=OTP_CONFIG.get("expires_in", 300))
                except Exception:
                    otp_code = None
                    
    if not otp_code:
        otp_len = OTP_CONFIG.get("otp_length", 6)
        if otp_len == 8:
            otp_code = f"{random.randint(10000000, 99999999)}"
        else:
            otp_code = f"{random.randint(100000, 999999)}"
            
        save_otp(
            email=email, 
            otp_code=otp_code, 
            store_method=store_method, 
            expires_in_seconds=OTP_CONFIG.get("expires_in", 300),
            secret_key=secret_key
        )
    
    success, dev_mode, error_message = send_otp_email(email, otp_code)
    if not success:
        return jsonify({
            "success": False,
            "error": f"Failed to send verification email. {error_message or ''}".strip()
        }), 500
    
    return jsonify({
        "success": True
    })


@app.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp_route():
    data = request.json or {}
    email = data.get("email", "").strip()
    otp_code = data.get("otp", "").strip()
    
    if not email or not otp_code:
        return jsonify({"success": False, "error": "Email and OTP are required"}), 400
        
    if "@" not in email:
        email += "@gmail.com"
        
    is_valid, error_code = verify_otp_status(
        email=email, 
        otp_code=otp_code, 
        allowed_attempts=OTP_CONFIG.get("allowed_attempts", 3),
        secret_key=app.secret_key
    )
    if not is_valid:
        if error_code == "TOO_MANY_ATTEMPTS":
            return jsonify({
                "success": False, 
                "error": "TOO_MANY_ATTEMPTS",
                "message": "Too many failed verification attempts. This code is now invalid. Please request a new one."
            }), 429
        return jsonify({"success": False, "error": "Invalid or expired verification code"}), 400
        
    user_id = create_user(email)
    
    # Store session details
    guest_id = session.get("guest_id")
    session.clear()
    session["user_id"] = user_id
    session["user_email"] = email
    session["is_guest"] = False
    
    # If there was a guest history, migrate it to the logged in user
    migrate_guest_history(guest_id, user_id)
    
    # Auto-send email copies of user's lab reports to their Gmail address
    try:
        user_history = load_history_for_user(user_id)
        if user_history:
            for item in user_history[:3]:
                threading.Thread(
                    target=send_report_email,
                    args=(email, item.get("title", "Lab Report Analysis"), item.get("analysis", ""))
                ).start()
    except Exception as e:
        print(f"Error sending report to Gmail: {e}")
        
    return jsonify({"success": True})


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
        identifier = session.get("user_id") or session.get("guest_id")
        if not identifier:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        delete_history_item_for_user(identifier, item_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


DEFAULT_MOCK_TRENDS = {
    "Glucose": [
        {"date": "2026-06-01", "value": 94, "value_str": "94 mg/dL", "range": "70-99 mg/dL", "status": "normal"},
        {"date": "2026-07-01", "value": 112, "value_str": "112 mg/dL", "range": "70-99 mg/dL", "status": "high"},
        {"date": "2026-07-14", "value": 98, "value_str": "98 mg/dL", "range": "70-99 mg/dL", "status": "normal"}
    ],
    "Cholesterol": [
        {"date": "2026-06-01", "value": 178, "value_str": "178 mg/dL", "range": "< 200 mg/dL", "status": "normal"},
        {"date": "2026-07-01", "value": 224, "value_str": "224 mg/dL", "range": "< 200 mg/dL", "status": "high"},
        {"date": "2026-07-14", "value": 196, "value_str": "196 mg/dL", "range": "< 200 mg/dL", "status": "normal"}
    ],
    "HbA1c": [
        {"date": "2026-06-01", "value": 5.4, "value_str": "5.4%", "range": "4.0-5.6%", "status": "normal"},
        {"date": "2026-07-01", "value": 5.9, "value_str": "5.9%", "range": "4.0-5.6%", "status": "high"},
        {"date": "2026-07-14", "value": 5.5, "value_str": "5.5%", "range": "4.0-5.6%", "status": "normal"}
    ]
}


def build_trends_from_history(raw_history):
    trends = {}
    for item in raw_history:
        analysis = item.get("analysis") or ""
        date_raw = item.get("timestamp_display") or item.get("timestamp") or ""
        date_str = date_raw.split(" ")[0].split("T")[0] if date_raw else "2026-07-01"
        
        lines = analysis.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            match = re.search(r"[\-\*•]?\s*\*\*([^\*:]+)\*\*:\s*([0-9\.]+(?:\s*[A-Za-z/\%]+)?)(?:\s*\((?:Reference Range:\s*)?([^\)]+)\))?\s*(?:[\-\—\–]\s*(.+))?", line, re.IGNORECASE)
            if not match:
                match = re.search(r"[\-\*•]?\s*([A-Za-z0-9\s,\/\-\+]+):\s*([0-9\.]+(?:\s*[A-Za-z/\%]+)?)(?:\s*\((?:Reference Range:\s*)?([^\)]+)\))?\s*(?:[\-\—\–]\s*(.+))?", line, re.IGNORECASE)
                
            if match:
                param = match.group(1).strip()
                val_raw = match.group(2).strip()
                rng = (match.group(3) or "").strip()
                status_raw = (match.group(4) or "").strip()
                
                if len(param) < 2 or param.lower() in ["note", "comments", "test", "name", "date", "final report"]:
                    continue
                    
                num_match = re.search(r"([0-9\.]+)", val_raw)
                if not num_match:
                    continue
                try:
                    num_val = float(num_match.group(1))
                except ValueError:
                    continue
                    
                status = "normal"
                if "high" in status_raw.lower() or "🔴" in status_raw:
                    status = "high"
                elif "low" in status_raw.lower() or "⚠️" in status_raw:
                    status = "low"
                    
                if param not in trends:
                    trends[param] = []
                    
                if not any(p["date"] == date_str and p["value"] == num_val for p in trends[param]):
                    trends[param].append({
                        "date": date_str,
                        "value": num_val,
                        "value_str": val_raw,
                        "range": rng,
                        "status": status
                    })
    
    for param in trends:
        trends[param].sort(key=lambda x: x["date"])
        
    return trends


@app.route("/api/trends")
def get_trends():
    raw_history = load_history()
    trends = build_trends_from_history(raw_history)
    if not trends:
        trends = DEFAULT_MOCK_TRENDS
    return jsonify({"success": True, "trends": trends})


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
                try:
                    with open(filepath, "rb") as f:
                        img_base64 = base64.b64encode(f.read()).decode("utf-8")
                except Exception as e:
                    print(f"Error encoding image base64: {e}")
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
            error_msg = re.sub(r"^\[(?:PDF\s+)?(?:OCR\s+)?ERROR:\s*", "", extracted_text).rstrip("]")
            if "tesseract not found" in error_msg.lower() or "tesseract is not installed" in error_msg.lower():
                error_msg = "Tesseract OCR binary is missing on the server. Please install Tesseract (e.g. 'brew install tesseract' or 'apt-get install tesseract-ocr') or paste the text directly."
            return jsonify({"success": False, "error": error_msg}), 400

    user_email = session.get("user_email")
    identifier = session.get("user_id") or session.get("guest_id")

    def generate_stream():
        yield json.dumps({"event": "extracted_text", "text": extracted_text}) + "\n"
        
        prompt = f"Report Text Content:\n{extracted_text}" if extracted_text else "Please analyze this medical report image:"
        if question:
            prompt += f"\n\nFocus especially on this question from the user: {question}"

        analysis = ""
        try:
            for token in generate_stream_llm(prompt, system_prompt=SYSTEM_PROMPT, img_base64=img_base64):
                analysis += token
                yield json.dumps({"event": "token", "text": token}) + "\n"
        except Exception as e:
            yield json.dumps({"event": "error", "error": f"AI streaming error: {str(e)}"}) + "\n"
            return

        if not analysis.strip():
            yield json.dumps({"event": "error", "error": "No response received from AI engine."}) + "\n"
            return

        if analysis.startswith("[ERROR:") or analysis.startswith("[API ERROR:"):
            err_msg = analysis.replace("[ERROR:", "").replace("[API ERROR:", "").rstrip("]")
            yield json.dumps({"event": "error", "error": err_msg.strip()}) + "\n"
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
        
        try:
            save_history(history_entry, identifier=identifier)
        except Exception as db_err:
            print(f"Error saving history: {db_err}")

        if user_email:
            try:
                threading.Thread(
                    target=send_report_email,
                    args=(user_email, title, analysis)
                ).start()
            except Exception as mail_err:
                print(f"Error launching email thread: {mail_err}")
        
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
            try:
                for token in generate_stream_llm(question, system_prompt=system_prompt, messages_history=history):
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
