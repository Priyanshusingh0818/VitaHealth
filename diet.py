# app.py
from flask import Flask, render_template, request, send_file
import os
from groq import Groq
import json
from fpdf import FPDF
from datetime import datetime, timedelta
import io
from tensorflow.keras.models import load_model


app = Flask(__name__)

# Configure Groq client
client = Groq(api_key="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")
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/recommend', methods=['POST'])
def recommend():
    # Get user data from form
    name = request.form.get('name')
    age = request.form.get('age')
    weight = request.form.get('weight')
    height = request.form.get('height')
    gender = request.form.get('gender')
    activity_level = request.form.get('activity_level')
    dietary_preferences = request.form.get('dietary_preferences')
    allergies = request.form.get('allergies')
    goals = request.form.get('goals')
    
    # Calculate BMI
    try:
        height_m = float(height) / 100  # convert cm to m
        weight_kg = float(weight)
        bmi = round(weight_kg / (height_m * height_m), 2)
    except:
        bmi = "Unable to calculate"
    
    # Generate prompt for Groq
    prompt = f"""You are a professional nutritionist. Create a detailed 7-day diet plan for the following person:

Name: {name}
Age: {age}
Weight: {weight} kg
Height: {height} cm
BMI: {bmi}
Gender: {gender}
Activity Level: {activity_level}
Dietary Preferences: {dietary_preferences}
Allergies/Restrictions: {allergies}
Goals: {goals}

For each day of the week (Monday through Sunday), provide:
1. Three main meals (breakfast, lunch, dinner)
2. Two snacks
3. Approximate calorie count for each meal and total daily calories
4. Hydration recommendation
5. A brief nutritional explanation for why this day's meals are beneficial

Format your response as valid JSON with the following structure:
{{
  "plan_overview": "Brief description of overall plan",
  "calorie_target": "Daily calorie target based on their stats",
  "daily_plans": [
    {{
      "day": "Monday",
      "meals": {{
        "breakfast": {{ "name": "Meal name", "description": "Ingredients and preparation", "calories": 000 }},
        "morning_snack": {{ "name": "Snack name", "description": "Simple description", "calories": 000 }},
        "lunch": {{ "name": "Meal name", "description": "Ingredients and preparation", "calories": 000 }},
        "afternoon_snack": {{ "name": "Snack name", "description": "Simple description", "calories": 000 }},
        "dinner": {{ "name": "Meal name", "description": "Ingredients and preparation", "calories": 000 }}
      }},
      "total_calories": 0000,
      "hydration": "Water recommendation",
      "nutritional_notes": "Brief explanation of nutritional benefits"
    }},
    ...repeat for all 7 days...
  ],
  "general_advice": "Overall nutrition and diet advice"
}}

Make all recommendations evidence-based and appropriate for the person's goals and restrictions.
"""

    # Call Groq API
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert nutritionist AI assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        # Parse the response
        response_text = completion.choices[0].message.content
        diet_plan = extract_json(response_text)
        
        # Generate dates for the current week
        today = datetime.now()
        dates = []
        for i in range(7):
            day = today + timedelta(days=i)
            dates.append(day.strftime("%A, %B %d, %Y"))
        
        # Generate PDF
        pdf_data = generate_pdf(diet_plan, name, age, weight, height, gender, activity_level, 
                     dietary_preferences, allergies, goals, bmi, dates)
        
        return render_template('result.html', 
                            plan=diet_plan, 
                            user_info={
                                'name': name,
                                'age': age,
                                'weight': weight,
                                'height': height,
                                'gender': gender,
                                'bmi': bmi,
                                'activity_level': activity_level,
                                'dietary_preferences': dietary_preferences,
                                'allergies': allergies,
                                'goals': goals
                            },
                            dates=dates)
                            
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/download_pdf')
def download_pdf():
    # Get all the user data and plan from the query parameters
    # In a production environment, you should store this temporarily in a session
    # and retrieve it here to avoid URL length limitations
    
    name = request.args.get('name')
    age = request.args.get('age')
    weight = request.args.get('weight')
    height = request.args.get('height')
    gender = request.args.get('gender')
    bmi = request.args.get('bmi')
    activity_level = request.args.get('activity_level')
    dietary_preferences = request.args.get('dietary_preferences')
    allergies = request.args.get('allergies')
    goals = request.args.get('goals')
    
    # This is not the best approach, but for demonstration purposes:
    # In a real app, you would store the plan in a session or database
    plan_json = request.args.get('plan')
    if plan_json:
        plan = json.loads(plan_json)
    else:
        # Fallback if plan data is not available
        return "Error: Diet plan data not available", 400
    
    # Generate dates for the current week
    today = datetime.now()
    dates = []
    for i in range(7):
        day = today + timedelta(days=i)
        dates.append(day.strftime("%A, %B %d, %Y"))
    
    # Generate PDF
    pdf_data = generate_pdf(plan, name, age, weight, height, gender, activity_level, 
                 dietary_preferences, allergies, goals, bmi, dates)
    
    # Create in-memory file-like object
    pdf_io = io.BytesIO(pdf_data)
    pdf_io.seek(0)
    
    # Return the PDF as a downloadable file
    return send_file(
        pdf_io,
        mimetype='application/pdf',
        download_name=f'Diet_Plan_{name}.pdf',
        as_attachment=True
    )

def extract_json(text):
    """Extract JSON from text even if there's surrounding text"""
    try:
        # First try to parse the entire text as JSON
        return json.loads(text)
    except:
        # If that fails, try to find JSON within the text
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > 0:
                return json.loads(text[start:end])
        except:
            pass
    
    # If all parsing fails, return a helpful error message
    return {
        "error": "Failed to parse response as JSON",
        "raw_response": text
    }

def generate_pdf(diet_plan, name, age, weight, height, gender, activity_level, 
                dietary_preferences, allergies, goals, bmi, dates):
    """Generate a PDF with the diet plan"""
    class PDF(FPDF):
        def header(self):
            # Logo
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, '7-Day Personalized Diet Plan', 0, 1, 'C')
            self.line(10, 18, 200, 18)
            self.ln(10)
        
        def footer(self):
            # Page number
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    pdf = PDF()
    pdf.add_page()
    
    # User Information
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Personal Information:', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f'Name: {name}', 0, 1)
    pdf.cell(0, 5, f'Age: {age}  |  Weight: {weight} kg  |  Height: {height} cm  |  BMI: {bmi}', 0, 1)
    pdf.cell(0, 5, f'Gender: {gender}  |  Activity Level: {activity_level}', 0, 1)
    pdf.cell(0, 5, f'Dietary Preferences: {dietary_preferences}', 0, 1)
    pdf.cell(0, 5, f'Allergies/Restrictions: {allergies}', 0, 1)
    pdf.cell(0, 5, f'Goals: {goals}', 0, 1)
    pdf.ln(5)
    
    # Plan Overview
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Plan Overview:', 0, 1)
    pdf.set_font('Arial', '', 10)
    if 'plan_overview' in diet_plan:
        pdf.multi_cell(0, 5, diet_plan['plan_overview'])
    if 'calorie_target' in diet_plan:
        pdf.cell(0, 5, f"Daily Calorie Target: {diet_plan['calorie_target']}", 0, 1)
    pdf.ln(5)
    
    # Daily Plans
    if 'daily_plans' in diet_plan:
        day_index = 0
        for day_plan in diet_plan['daily_plans']:
            if day_index >= 7:  # Ensure we only process up to 7 days
                break
                
            pdf.add_page()
            
            # Day Header
            pdf.set_font('Arial', 'B', 14)
            date_str = dates[day_index] if day_index < len(dates) else "Day " + str(day_index + 1)
            pdf.cell(0, 10, f"Day {day_index + 1}: {day_plan.get('day', '')} ({date_str})", 0, 1)
            pdf.ln(2)
            
            # Meals
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 8, 'Meals:', 0, 1)
            
            if 'meals' in day_plan:
                meals = day_plan['meals']
                
                # Breakfast
                if 'breakfast' in meals:
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 8, 'Breakfast:', 0, 1)
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(0, 5, f"- {meals['breakfast'].get('name', '')}", 0, 1)  # Changed bullet to hyphen
                    pdf.multi_cell(0, 5, f"{meals['breakfast'].get('description', '')}")
                    pdf.cell(0, 5, f"Calories: {meals['breakfast'].get('calories', '')}", 0, 1)
                    pdf.ln(2)
                
                # Morning Snack
                if 'morning_snack' in meals:
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 8, 'Morning Snack:', 0, 1)
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(0, 5, f"- {meals['morning_snack'].get('name', '')}", 0, 1)  # Changed bullet to hyphen
                    pdf.multi_cell(0, 5, f"{meals['morning_snack'].get('description', '')}")
                    pdf.cell(0, 5, f"Calories: {meals['morning_snack'].get('calories', '')}", 0, 1)
                    pdf.ln(2)
                
                # Lunch
                if 'lunch' in meals:
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 8, 'Lunch:', 0, 1)
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(0, 5, f"- {meals['lunch'].get('name', '')}", 0, 1)  # Changed bullet to hyphen
                    pdf.multi_cell(0, 5, f"{meals['lunch'].get('description', '')}")
                    pdf.cell(0, 5, f"Calories: {meals['lunch'].get('calories', '')}", 0, 1)
                    pdf.ln(2)
                
                # Afternoon Snack
                if 'afternoon_snack' in meals:
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 8, 'Afternoon Snack:', 0, 1)
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(0, 5, f"- {meals['afternoon_snack'].get('name', '')}", 0, 1)  # Changed bullet to hyphen
                    pdf.multi_cell(0, 5, f"{meals['afternoon_snack'].get('description', '')}")
                    pdf.cell(0, 5, f"Calories: {meals['afternoon_snack'].get('calories', '')}", 0, 1)
                    pdf.ln(2)
                
                # Dinner
                if 'dinner' in meals:
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 8, 'Dinner:', 0, 1)
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(0, 5, f"- {meals['dinner'].get('name', '')}", 0, 1)  # Changed bullet to hyphen
                    pdf.multi_cell(0, 5, f"{meals['dinner'].get('description', '')}")
                    pdf.cell(0, 5, f"Calories: {meals['dinner'].get('calories', '')}", 0, 1)
                    pdf.ln(2)
            
            # Daily Summary
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(0, 8, 'Daily Summary:', 0, 1)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 5, f"Total Calories: {day_plan.get('total_calories', '')}", 0, 1)
            pdf.cell(0, 5, f"Hydration: {day_plan.get('hydration', '')}", 0, 1)
            pdf.ln(2)
            
            # Nutritional Notes
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(0, 8, 'Nutritional Notes:', 0, 1)
            pdf.set_font('Arial', '', 10)
            pdf.multi_cell(0, 5, day_plan.get('nutritional_notes', ''))
            
            day_index += 1
    
    # General Advice
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'General Advice:', 0, 1)
    pdf.set_font('Arial', '', 10)
    if 'general_advice' in diet_plan:
        pdf.multi_cell(0, 5, diet_plan['general_advice'])
    
    # Disclaimer
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 8)
    pdf.multi_cell(0, 4, 'Disclaimer: This diet plan is generated by an AI assistant and should be used as '
                         'general guidance only. Please consult with a registered dietitian or healthcare '
                         'professional before making significant changes to your diet, especially if you '
                         'have any health conditions or concerns.')
    
    # Return PDF content as bytes
    try:
        return pdf.output(dest='S').encode('latin-1')
    except UnicodeEncodeError:
        # If there's an encoding error, try to handle it by replacing problematic characters
        return pdf.output(dest='S').encode('latin-1', errors='replace')
if __name__ == '__main__':
    app.run(debug=True, port=5000)