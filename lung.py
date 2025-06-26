from flask import Flask, render_template, request, jsonify
from tensorflow.keras.models import load_model
import cv2
import numpy as np
import os
import time
import uuid

app = Flask(__name__)
model = load_model("lung_cancer_detection_model.h5")

# Define categories and their descriptions/advice
categories = ["Benign cases", "Malignant cases", "Normal cases"]

# Health advice for each category
health_advice = {
    "Benign cases": [
        "Schedule a follow-up appointment with a pulmonologist for further evaluation",
        "Maintain a healthy diet rich in antioxidants like fruits and vegetables",
        "Consider quitting smoking if you're a smoker - it's never too late to benefit from quitting",
        "Practice regular moderate exercise to improve lung function",
        "Keep track of any changes in symptoms and maintain a health journal",
        "Explore stress reduction techniques like meditation or yoga as stress can impact recovery"
    ],
    "Malignant cases": [
        "Seek immediate consultation with an oncologist specialized in lung cancer",
        "Discuss comprehensive treatment plans including surgery, radiation, or chemotherapy",
        "Consider joining a cancer support group for emotional and psychological support",
        "Focus on nutritional needs - protein-rich foods can help maintain strength during treatment",
        "Prepare a list of questions for your healthcare team about your specific condition",
        "Look into clinical trials that might be available for your specific type of lung cancer"
    ],
    "Normal cases": [
        "Continue regular health check-ups to monitor lung health",
        "Maintain a smoke-free lifestyle to preserve lung function",
        "Stay physically active with aerobic exercises to support respiratory health",
        "Consider air quality in your home and workplace, use air purifiers if needed",
        "Stay up to date with vaccinations, especially those that prevent respiratory infections",
        "Maintain a balanced diet rich in foods that support lung health such as apples and leafy greens"
    ]
}

def prepare_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return None
    img = cv2.resize(img, (224, 224))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img / 255.0
    img = np.expand_dims(img, axis=0)
    return img

@app.route("/", methods=["GET", "POST"])
def upload():
    prediction = None
    advice = None
    image_path = None
    confidence = None
    
    if request.method == "POST":
        file = request.files["image"]
        if file:
            # Create a unique filename to prevent caching issues
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            
            if not os.path.exists("static/uploads"):
                os.makedirs("static/uploads")
            
            path = os.path.join("static/uploads", unique_filename)
            file.save(path)
            
            img = prepare_image(path)
            if img is not None:
                # Get model prediction
                pred = model.predict(img)
                predicted_class_index = np.argmax(pred)
                predicted_class = categories[predicted_class_index]
                
                # Calculate confidence percentage
                confidence = float(pred[0][predicted_class_index]) * 100
                
                # Get relevant health advice
                advice = health_advice[predicted_class]
                
                # Create prediction message
                prediction = {
                    "class": predicted_class,
                    "confidence": confidence,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                image_path = path
            else:
                prediction = {"error": "Failed to process the image."}
    
    return render_template("lung.html", 
                          prediction=prediction, 
                          advice=advice, 
                          image_path=image_path,
                          all_categories=categories)

@app.route("/api/predict", methods=["POST"])
def api_predict():
    """API endpoint for predictions"""
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400
    
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No image selected"}), 400
    
    # Save and process the image
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    if not os.path.exists("static/uploads"):
        os.makedirs("static/uploads")
    path = os.path.join("static/uploads", unique_filename)
    file.save(path)
    
    img = prepare_image(path)
    if img is None:
        return jsonify({"error": "Failed to process the image"}), 500
    
    # Get prediction
    pred = model.predict(img)
    predicted_class_index = np.argmax(pred)
    predicted_class = categories[predicted_class_index]
    confidence = float(pred[0][predicted_class_index]) * 100
    
    return jsonify({
        "prediction": predicted_class,
        "confidence": confidence,
        "advice": health_advice[predicted_class],
        "image_path": path
    })

if __name__ == '__main__':
    app.run(debug=True, port=5004)