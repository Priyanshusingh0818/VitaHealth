from flask import Flask, request, jsonify, render_template, abort
import os
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from werkzeug.utils import secure_filename
import traceback
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("pneumonia_app.log"),
                              logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max upload
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load the model
try:
    model_path = 'pneumonia_detection.h5'
    model = load_model(model_path)
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {str(e)}")
    logger.error(traceback.format_exc())
    model = None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def preprocess_image(img_path):
    """Preprocess image for the model"""
    try:
        # Load as RGB even if the image is grayscale
        img = image.load_img(img_path, target_size=(256, 256), color_mode='rgb')
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = img_array / 255.0  # Normalize pixel values
        return img_array
    except Exception as e:
        logger.error(f"Error preprocessing image: {str(e)}")
        logger.error(traceback.format_exc())
        raise

@app.route('/')
def home():
    return render_template('pnu.html')

@app.route('/predict', methods=['POST'])
def predict():
    # Check if model is loaded
    if model is None:
        logger.error("Model is not loaded")
        return jsonify({'error': 'Model is not available'}), 500
    
    # Check if image is in the request
    if 'image' not in request.files:
        logger.warning("No image file in request")
        return jsonify({'error': 'No image file provided'}), 400
    
    file = request.files['image']
    
    # Check if file is empty
    if file.filename == '':
        logger.warning("Empty file submitted")
        return jsonify({'error': 'No selected file'}), 400
    
    # Check if file type is allowed
    if not allowed_file(file.filename):
        logger.warning(f"Invalid file type: {file.filename}")
        return jsonify({'error': 'File type not allowed'}), 400
    
    try:
        # Save file to uploads folder
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        logger.info(f"File saved: {file_path}")
        
        # Preprocess the image
        processed_image = preprocess_image(file_path)
        
        # Make prediction
        prediction = model.predict(processed_image)
        
        # Get probabilities (assuming binary classification)
        pneumonia_prob = float(prediction[0][0])
        normal_prob = 1 - pneumonia_prob
        
        # Determine prediction class
        prediction_class = 'PNEUMONIA' if pneumonia_prob > 0.5 else 'NORMAL'
        
        # Create response
        result = {
            'prediction': prediction_class,
            'probabilities': {
                'PNEUMONIA': pneumonia_prob,
                'NORMAL': normal_prob
            }
        }
        
        logger.info(f"Prediction complete: {prediction_class} with confidence {max(pneumonia_prob, normal_prob):.2f}")
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error during prediction: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'An error occurred during processing'}), 500
    finally:
        # Clean up - optional: remove file after processing
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"File removed: {file_path}")
        except Exception as e:
            logger.error(f"Error removing file: {str(e)}")

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large (max 10MB)'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)