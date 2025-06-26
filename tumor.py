import os
import json
import logging
import numpy as np
import cv2
from flask import Flask, request, jsonify, render_template
import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load model configuration
try:
    with open("model_config.json", "r") as f:
        model_config = json.load(f)
    IMG_SIZE = model_config["img_size"]
    categories = model_config["categories"]
    logger.info(f"Loaded model configuration: IMG_SIZE={IMG_SIZE}, categories={categories}")
except Exception as e:
    # Default values if config file not found
    IMG_SIZE = 150
    categories = ["Glioma", "Meningioma", "Notumor", "Pituitary"]
    logger.warning(f"Could not load model configuration, using defaults: {e}")

# Define advice for each tumor type
tumor_advice = {
    "Glioma": [
        "Consult with a neuro-oncologist to discuss treatment options such as surgery, radiation, and chemotherapy",
        "Consider genetic testing to identify specific tumor mutations that may respond to targeted therapies",
        "Join a glioma support group to connect with others facing similar challenges",
        "Maintain a brain-healthy diet rich in antioxidants and omega-3 fatty acids",
        "Discuss seizure management strategies with your neurologist",
        "Ask about clinical trials that may be appropriate for your specific glioma subtype"
    ],
    "Meningioma": [
        "Discuss observation vs. treatment with your neurosurgeon as many meningiomas grow slowly",
        "Consider getting a second opinion before proceeding with any surgical intervention",
        "Request regular MRI monitoring to track tumor growth over time",
        "Inquire about stereotactic radiosurgery options if conventional surgery is risky",
        "Track and report any new or worsening neurological symptoms to your doctor immediately",
        "Maintain healthy blood pressure as hypertension may worsen symptoms"
    ],
    "Pituitary": [
        "Consult with an endocrinologist to evaluate and manage potential hormonal imbalances",
        "Keep a symptom diary to track changes in vision, headaches, and other symptoms",
        "Discuss medication options that might shrink the tumor or control hormone production",
        "Ask about transsphenoidal surgery which accesses the tumor through the nasal cavity",
        "Request regular vision tests as pituitary tumors can affect the optic nerves",
        "Consider joining a pituitary disorder support group for additional resources"
    ],
    "Notumor": [
        "Continue with regular health check-ups as recommended by your physician",
        "Maintain a healthy lifestyle with balanced nutrition and regular exercise",
        "Consider follow-up imaging in 6-12 months to ensure continued health",
        "Be aware of any new neurological symptoms and report them to your doctor",
        "Keep managing other health conditions that may have similar symptoms",
        "Focus on stress management techniques to maintain neurological health"
    ]
}

# Global variable for the model
model = None

def load_model_from_file():
    """
    Load the model and return it, or None if it fails
    """
    global model
    try:
        model = load_model("brain_tumor_model.h5")
        logger.info("Model loaded successfully")
        logger.info(f"Model expects input shape: {model.input_shape}")
        return model
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None

# Load the model when the application starts
model = load_model_from_file()

def preprocess_image(image_data):
    """
    Preprocess the image to match the model's expected input
    """
    try:
        # Convert bytes to image if needed
        if isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data))
            image = np.array(image)
        else:
            image = image_data
            
        # Make sure image is in RGB format
        if len(image.shape) == 2:  # Grayscale to RGB
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:  # RGBA to RGB
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            
        # Resize to expected input size (THIS IS CRITICAL)
        image = cv2.resize(image, (IMG_SIZE, IMG_SIZE))
        
        # Normalize pixel values
        image = image / 255.0
        
        # Add batch dimension
        image = np.expand_dims(image, axis=0)
        
        logger.info(f"Preprocessed image shape: {image.shape}")
        return image
        
    except Exception as e:
        logger.error(f"Error preprocessing image: {e}")
        raise

@app.route('/')
def home():
    return render_template('tumor.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        global model
        
        # Check if model is loaded, if not try to load it
        if model is None:
            model = load_model_from_file()
            if model is None:
                return jsonify({'error': 'Model could not be loaded'})
        
        # Get image from request
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'})
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'})
            
        # Read and preprocess the image
        image_bytes = file.read()
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        processed_image = preprocess_image(image)
        
        # Make prediction
        logger.info(f"Preprocessed image shape: {processed_image.shape}")
        
        # Double-check shape before prediction
        if processed_image.shape[1:3] != (IMG_SIZE, IMG_SIZE):
            logger.info(f"Reshaping image from {processed_image.shape} to match (None, {IMG_SIZE}, {IMG_SIZE}, 3)")
            processed_image = cv2.resize(processed_image[0], (IMG_SIZE, IMG_SIZE))
            processed_image = np.expand_dims(processed_image, axis=0)
        
        # Make prediction
        try:
            predictions = model.predict(processed_image)
            predicted_class = np.argmax(predictions[0])
            confidence = float(predictions[0][predicted_class])
            predicted_category = categories[predicted_class]
            
            # Get advice for the predicted tumor type
            advice = tumor_advice.get(predicted_category, [])
            
            result = {
                'class': predicted_category,
                'confidence': confidence * 100,
                'predictions': {categories[i]: float(pred) for i, pred in enumerate(predictions[0])},
                'advice': advice
            }
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            return jsonify({'error': str(e)})
            
    except Exception as e:
        logger.error(f"ValueError in prediction: {e}")
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5005)