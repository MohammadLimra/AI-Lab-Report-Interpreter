import os
import random
import smtplib
from email.message import EmailMessage
from dotenv import load_data  # Import dotenv

# Load the variables from the .env file
load_dotenv()

otp = ""
for i in range(6):
    otp += str(random.randint(0,9))

server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()

# Fetch the credentials safely from the environment
from_mail = os.getenv('EMAIL_USER')
app_password = os.getenv('EMAIL_PASS')

server.login(from_mail, app_password)
to_mail = input("Enter your email: ")

msg = EmailMessage()
msg['Subject'] = "OTP Verification"
msg['From'] = from_mail
msg['To'] = to_mail
msg.set_content("Your OTP is: " + otp)

server.send_message(msg)

input_otp = input("Enter OTP: ")
if input_otp == otp:
    print("OTP verified successfully")
else:
    print("Invalid OTP")
