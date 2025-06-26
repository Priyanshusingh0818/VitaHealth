from flask import Flask, render_template, send_from_directory, redirect, url_for, request, jsonify
import os
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

handler = RotatingFileHandler('logs/app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Create templates and static folders if they don't exist
for folder in ['templates', 'static']:
    if not os.path.exists(folder):
        os.makedirs(folder)
        app.logger.info(f"Created {folder} directory")

# Check if landing.html exists
landing_html_path = os.path.join(app.root_path, 'templates', 'landing.html')
if not os.path.exists(landing_html_path):
    app.logger.warning(f"landing.html not found at {landing_html_path}")

@app.route('/')
def home():
    try:
        app.logger.info("Home page accessed")
        return render_template('landing.html')
    except Exception as e:
        app.logger.error(f"Error serving home page: {str(e)}")
        return render_error("Error loading home page. Please try again later.")

@app.route('/diagnose')
def diagnose():
    try:
        app.logger.info("Diagnose page accessed")
        return render_template('landing.html')
    except Exception as e:
        app.logger.error(f"Error serving diagnose page: {str(e)}")
        return render_error("Error loading diagnose page. Please try again later.")

# Redirect routes for different services
@app.route('/diet')
def diet():
    try:
        app.logger.info("Redirecting to diet service")
        return redirect('http://localhost:5000/index.html')
    except Exception as e:
        app.logger.error(f"Error redirecting to diet service: {str(e)}")
        return render_error("Error redirecting to diet service.")

@app.route('/chat')
def chat():
    try:
        app.logger.info("Redirecting to chat service")
        return redirect('http://localhost:5002/chat.html')
    except Exception as e:
        app.logger.error(f"Error redirecting to chat service: {str(e)}")
        return render_error("Error redirecting to chat service.")

@app.route('/medicine')
def medicine():
    try:
        app.logger.info("Redirecting to medicine service")
        return redirect('http://localhost:5003/medi.html')
    except Exception as e:
        app.logger.error(f"Error redirecting to medicine service: {str(e)}")
        return render_error("Error redirecting to medicine service.")

# Redirect routes for disease diagnosis
@app.route('/diagnose/brain-tumor')
def brain_tumor():
    try:
        app.logger.info("Redirecting to brain tumor diagnosis")
        return redirect('http://localhost:5005/tumor.html')
    except Exception as e:
        app.logger.error(f"Error redirecting to brain tumor diagnosis: {str(e)}")
        return render_error("Error redirecting to brain tumor diagnosis.")

@app.route('/diagnose/lung-cancer')
def lung_cancer():
    try:
        app.logger.info("Redirecting to lung cancer diagnosis")
        return redirect('http://localhost:5004/lung.html')
    except Exception as e:
        app.logger.error(f"Error redirecting to lung cancer diagnosis: {str(e)}")
        return render_error("Error redirecting to lung cancer diagnosis.")

@app.route('/diagnose/pneumonia')
def pneumonia():
    try:
        app.logger.info("Redirecting to pneumonia diagnosis")
        return redirect('http://localhost:5001/pne.html')  # Updated from 5006 to 5001 as requested
    except Exception as e:
        app.logger.error(f"Error redirecting to pneumonia diagnosis: {str(e)}")
        return render_error("Error redirecting to pneumonia diagnosis.")

# Error handling
def render_error(message):
    return render_template('error.html', error_message=message), 500

@app.errorhandler(404)
def page_not_found(e):
    app.logger.warning(f"Page not found: {request.path}")
    return render_template('error.html', error_message="Page not found."), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"Internal server error: {str(e)}")
    return render_template('error.html', error_message="Internal server error."), 500

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.logger.info("Application starting")
    app.run(host='0.0.0.0', port=5007, debug=True)