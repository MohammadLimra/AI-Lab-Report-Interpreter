import os
import random
import smtplib
from email.message import EmailMessage
from flask import Flask, request, jsonify

app = Flask(__name__)

# Temporary dictionary to store generated OTPs for validation in memory
# Note: For real apps, you'd use a database like Redis or PostgreSQL
otp_store = {}

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    to_mail = data.get('email')
    
    if not to_mail:
        return jsonify({"error": "Email is required"}), 400

    # 1. Generate OTP
    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
    otp_store[to_mail] = otp # Save it to check later

    # 2. Get credentials safely from Railway
    from_mail = os.getenv('EMAIL_USER')
    app_password = os.getenv('EMAIL_PASS')

    try:
        # 3. Send the email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_mail, app_password)

        msg = EmailMessage()
        msg['Subject'] = "OTP Verification"
        msg['From'] = from_mail
        msg['To'] = to_mail
        msg.set_content(f"Your OTP is: {otp}")

        server.send_message(msg)
        server.quit()
        
        return jsonify({"message": "OTP sent successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    user_otp = data.get('otp')

    if not email or not user_otp:
        return jsonify({"error": "Email and OTP are required"}), 400

    # Check if OTP matches
    correct_otp = otp_store.get(email)
    if correct_otp and user_otp == correct_otp:
        del otp_store[email] # Clear it after successful verification
        return jsonify({"status": "OTP verified successfully"}), 200
    else:
        return jsonify({"status": "Invalid OTP"}), 400

if __name__ == "__main__":
    # Crucial for Railway: Must bind to 0.0.0.0 and the dynamic $PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
