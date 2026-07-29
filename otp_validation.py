import os
import random
import requests
from dotenv import load_dotenv

load_dotenv()

# 1. Generate a 6-digit random OTP
otp = "".join([str(random.randint(0, 9)) for _ in range(6)])

# 2. Grab Brevo credentials from environment (.env)
brevo_api_key = os.getenv("BREVO_API_KEY")
sender_email = os.getenv("BREVO_SENDER_EMAIL")
sender_name = os.getenv("BREVO_SENDER_NAME", "AI Report Interpreter")

if not brevo_api_key or not sender_email:
    print("Error: BREVO_API_KEY or BREVO_SENDER_EMAIL environment variables are missing from .env!")
    exit(1)

# 3. Ask for recipient email
to_mail = input("Enter your email: ")

# 4. Send via Brevo API
try:
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": brevo_api_key,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_mail}],
        "subject": "OTP Verification",
        "htmlContent": f"<p>Your OTP is: <strong>{otp}</strong></p>"
    }
    
    res = requests.post(url, headers=headers, json=payload, timeout=10)
    if res.status_code in (200, 201, 202):
        print("Email sent successfully via Brevo!")
        
        # 5. Verify the user input
        input_otp = input("Enter OTP: ")
        if input_otp == otp:
            print("OTP verified successfully")
        else:
            print("Invalid OTP")
    else:
        print(f"Failed to send email. Brevo response: {res.text}")

except Exception as e:
    print(f"An error occurred: {e}")