**AI-Lab-Report_Interpreter** is a Flask-based web application designed to simplify the analysis of medical lab reports. It allows users to upload images or PDFs, extracts text using Optical Character Recognition (OCR), and analyzes the content with AI tools to provide medical insights. This tool automates the interpretation of lab data, saving time and improving efficiency for healthcare professionals.
 https://ai-lab-report-interpreter-resend-api.up.railway.app/

## Features
- **File Uploads**: Supports image (`png`, `jpg`, `jpeg`) and PDF formats.
- **OCR Integration**: Extracts text from images and PDFs using `pytesseract`.
- **AI Analysis**: Uses AI tools to analyze extracted text and provide medical insights.
- **Secure File Handling**: Ensures safe uploads with file size and type restrictions.
- **History Management**: Maintains a history of processed reports in `history.json`.
- **Web Interface**: User-friendly interface for uploading files and viewing results.

---

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/AI-Lab-Report_Interpreter.git
   cd AI-Lab-Report_Interpreter

2. Set Up a Virtual Environment (optional but recommended):
   python3 -m venv .venv
   source .venv/bin/activate

3. Install Dependencies:
   pip install -r requirements.txt

4. Install Tesseract-OCR: On macOS:
   brew install tesseract
   
5. Set Up Environment Variables: Create a .env file in the root directory and add:
   SECRET_KEY=your-secret-key
   
Usage
1. Run the Application:
   python3 app.py

2. Access the Web Interface: Open your browser and go to http://127.0.0.1:5002.

3. Upload Reports:
   Upload an image or PDF file.
   View extracted text and AI-generated insights.

Requirements
   Python 3.7 or higher
   Flask
  pytesseract
  Pillow
  pdf2image
  PyPDF2
  Tesseract-OCR 

Contributing
  Contributions are welcome! Feel free to submit issues or pull requests to improve the project.  

License
  This project is licensed under the MIT License. See the LICENSE file for details.  

Acknowledgments
  Flask for the web framework.
  Tesseract-OCR for text extraction.
  AI tools and libraries for analysis.
  
