from flask import Flask, request, jsonify, render_template
import os
import json
import uuid
import sqlite3
import re
import datetime
from groq import Groq

app = Flask(__name__)
app.secret_key = os.urandom(24) 

GROQ_API_KEY = "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"

groq_client = Groq(api_key=GROQ_API_KEY)

conversation_history = {}

# Database setup
def init_db():
    conn = sqlite3.connect('mental_health_app.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        message TEXT NOT NULL,
        response TEXT NOT NULL,
        sentiment_score REAL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mood_entries (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        mood_score INTEGER NOT NULL,
        mood_description TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS resources (
        id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        url TEXT NOT NULL,
        tags TEXT
    )
    ''')
    
    resources = [
        ('1', 'Crisis', 'National Suicide Prevention Lifeline', '24/7 support for people in distress', 'https://988lifeline.org/', 'suicide,crisis,emergency'),
        ('2', 'Crisis', 'Crisis Text Line', 'Text HOME to 741741', 'https://www.crisistextline.org/', 'crisis,text,emergency'),
        ('3', 'Support', 'NAMI HelpLine', 'Mental health information, resources, and support', 'https://www.nami.org/help', 'support,information,resources'),
        ('4', 'Self-help', 'Breathing Exercises', 'Simple breathing techniques for anxiety', '/breathing', 'anxiety,breathing,technique')
    ]
    
    cursor.executemany('INSERT OR IGNORE INTO resources VALUES (?, ?, ?, ?, ?, ?)', resources)
    
    conn.commit()
    conn.close()

init_db()

# Initialize user_info table
def init_user_info_table():
    conn = sqlite3.connect('mental_health_app.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_info (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize the table when app starts
init_user_info_table()

# Modified system prompt to encourage shorter responses and allow casual conversation
SYSTEM_PROMPT = """
You are MindfulAI, a mental health support assistant designed to provide empathetic responses and practical help.

IMPORTANT: Keep all responses very brief (2-3 sentences maximum). Users need concise, actionable support rather than lengthy explanations.

Your primary features:
- Active listening and validation of feelings
- Personalized coping strategies
- Evidence-based techniques from CBT, DBT, and positive psychology
- Crisis detection and appropriate intervention

Guidelines:
- Respond with brief empathy and warmth
- Provide specific, actionable strategies
- Maintain a hopeful but realistic tone
- NEVER claim to be a replacement for professional mental health care
- Be conversational and friendly - you can engage in casual chit-chat
- If the user wants to play a game, you can acknowledge this but gently suggest they try the app's mood tools or exercises instead

Response Framework (keep each point to 1-2 sentences):
1. Acknowledge - Briefly validate their feelings
2. Support - Offer one relevant coping strategy
3. Empower - One quick statement to encourage them

For crisis situations:
- Express immediate concern
- Provide crisis resources
- Emphasize the importance of professional help

Always keep responses short and focused on mental health support, while allowing for natural conversation flow.
"""

@app.route('/')
def redirect_to_chat():
    # Redirect root URL to chat page
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    
    # Use cookie for session tracking instead of login
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Initialize conversation history for new sessions
    if session_id not in conversation_history:
        conversation_history[session_id] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": "Hi there! I'm MindfulAI, your mental health companion. How are you feeling today?"}
        ]
    
    # Add user message to history
    conversation_history[session_id].append({"role": "user", "content": user_message})
    
    # Extract potential user information from chat
    extract_user_info(user_message, session_id)
    
    # Check for crisis keywords
    crisis_keywords = ["suicide", "kill myself", "end my life", "want to die", "harm myself", "self-harm"]
    
    if any(keyword in user_message.lower() for keyword in crisis_keywords):
        crisis_response = """I'm concerned about what you're sharing. Please reach out for immediate help:
- Call/text 988 (Suicide & Crisis Lifeline)
- Text HOME to 741741 (Crisis Text Line)
- Call emergency services (911)

You don't have to face these feelings alone."""

        conversation_history[session_id].append({"role": "assistant", "content": crisis_response})
        
        # Save to database
        chat_id = str(uuid.uuid4())
        conn = sqlite3.connect('mental_health_app.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO chat_history (id, session_id, message, response, sentiment_score) VALUES (?, ?, ?, ?, ?)',
            (chat_id, session_id, user_message, crisis_response, -9.0)  # Use -9.0 to flag crisis messages
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            "response": crisis_response,
            "is_crisis": True,
            "resources": get_crisis_resources(),
            "session_id": session_id
        })
    
    # Modified approach - don't redirect non-mental health messages, let the AI handle them naturally
    try:
        # Call Groq API for response
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=conversation_history[session_id],
            temperature=0.7,
            max_tokens=200,  # Reduced from 500 to get shorter responses
            top_p=1,
            stream=False,
        )
        
        bot_response = response.choices[0].message.content.strip()
        
        # Add bot response to history
        conversation_history[session_id].append({"role": "assistant", "content": bot_response})
        
        # Analyze sentiment (simple implementation)
        sentiment_score = analyze_sentiment(user_message)
        
        # Save to database
        chat_id = str(uuid.uuid4())
        conn = sqlite3.connect('mental_health_app.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO chat_history (id, session_id, message, response, sentiment_score) VALUES (?, ?, ?, ?, ?)',
            (chat_id, session_id, user_message, bot_response, sentiment_score)
        )
        conn.commit()
        conn.close()
        
        # Limit conversation history
        if len(conversation_history[session_id]) > 20:
            # Keep system message and trim older messages
            system_messages = [msg for msg in conversation_history[session_id] if msg["role"] == "system"]
            conversation_history[session_id] = system_messages + conversation_history[session_id][-17:]
        
        # Get relevant resources based on user message
        resources = get_relevant_resources(user_message)
        
        return jsonify({
            "response": bot_response, 
            "sentiment": sentiment_score,
            "resources": resources,
            "session_id": session_id
        })
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"response": "I'm having trouble processing your request. Please try again later."}), 500

def extract_user_info(message, session_id):
    """Extract potential user information from chat messages"""
    try:
        # Simple name extraction (very basic)
        name_patterns = [
            r"my name is (\w+)",
            r"i am (\w+)",
            r"i'm (\w+)",
            r"call me (\w+)"
        ]
        
        message_lower = message.lower()
        
        for pattern in name_patterns:
            match = re.search(pattern, message_lower)
            if match:
                name = match.group(1).capitalize()
                
                # Store the name
                conn = sqlite3.connect('mental_health_app.db')
                cursor = conn.cursor()
                
                info_id = str(uuid.uuid4())
                cursor.execute(
                    'INSERT OR REPLACE INTO user_info (id, session_id, key, value) VALUES (?, ?, ?, ?)',
                    (info_id, session_id, 'name', name)
                )
                
                conn.commit()
                conn.close()
                break
    
    except Exception as e:
        print(f"Error extracting user info: {str(e)}")

# Removed the is_mental_health_related function and its usage in the chat route

def analyze_sentiment(text):
    """Simple sentiment analysis - in a real app you'd use a proper NLP library or API"""
    # For demo purposes, just count positive and negative words
    positive_words = ["happy", "good", "great", "better", "joy", "excited", "calm", "relaxed", "peaceful", "hopeful"]
    negative_words = ["sad", "bad", "depressed", "anxious", "worried", "angry", "upset", "stress", "fear", "overwhelm"]
    
    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    # Scale from -5 to 5
    if positive_count == 0 and negative_count == 0:
        return 0
    return (positive_count - negative_count) / (positive_count + negative_count) * 5

def get_crisis_resources():
    """Return crisis resources"""
    return [
        {
            "title": "National Suicide Prevention Lifeline",
            "description": "24/7 support for people in distress",
            "url": "https://988lifeline.org/",
            "phone": "988"
        },
        {
            "title": "Crisis Text Line",
            "description": "Text support for people in crisis",
            "url": "https://www.crisistextline.org/",
            "phone": "Text HOME to 741741"
        },
        {
            "title": "Emergency Services",
            "description": "For immediate emergency assistance",
            "phone": "911"
        }
    ]

def get_relevant_resources(message):
    """Return relevant resources based on message content"""
    conn = sqlite3.connect('mental_health_app.db')
    cursor = conn.cursor()
    
    # Simple keyword matching
    keywords = {
        "anxiety": ["anxiety", "panic", "worry", "stress", "nervous"],
        "depression": ["depression", "sad", "hopeless", "low", "down"],
        "sleep": ["sleep", "insomnia", "tired", "rest", "bed"],
        "breathing": ["breathing", "breath", "calm", "relax", "peace"],
        "professional": ["therapist", "counselor", "psychiatrist", "professional", "doctor"]
    }
    
    message_lower = message.lower()
    matching_categories = []
    
    for category, words in keywords.items():
        if any(word in message_lower for word in words):
            matching_categories.append(category)
    
    # Get resources for matching categories
    resources = []
    if matching_categories:
        placeholders = ','.join(['?'] * len(matching_categories))
        cursor.execute(f"""
            SELECT id, category, title, description, url 
            FROM resources 
            WHERE category IN ({placeholders}) OR tags LIKE ?
            LIMIT 3
        """, matching_categories + ['%' + '%'.join(matching_categories) + '%'])
        
        for row in cursor.fetchall():
            resources.append({
                "id": row[0],
                "category": row[1],
                "title": row[2],
                "description": row[3],
                "url": row[4]
            })
    
    # If no matching resources or few results, add some general resources
    if len(resources) < 2:
        cursor.execute("""
            SELECT id, category, title, description, url 
            FROM resources 
            WHERE category = 'Self-help'
            LIMIT 3
        """)
        
        for row in cursor.fetchall():
            # Check if this resource is already in the list
            if not any(r['id'] == row[0] for r in resources):
                resources.append({
                    "id": row[0],
                    "category": row[1],
                    "title": row[2],
                    "description": row[3],
                    "url": row[4]
                })
    
    conn.close()
    return resources

@app.route('/api/mood', methods=['POST'])
def record_mood():
    data = request.get_json()
    mood_score = data.get('score')
    mood_description = data.get('description', '')
    session_id = request.cookies.get('session_id', str(uuid.uuid4()))
    
    if not mood_score or not isinstance(mood_score, int) or mood_score < 1 or mood_score > 10:
        return jsonify({"success": False, "message": "Invalid mood score. Please provide a number between 1 and 10"}), 400
    
    try:
        conn = sqlite3.connect('mental_health_app.db')
        cursor = conn.cursor()
        
        mood_id = str(uuid.uuid4())
        cursor.execute(
            'INSERT INTO mood_entries (id, session_id, mood_score, mood_description) VALUES (?, ?, ?, ?)',
            (mood_id, session_id, mood_score, mood_description)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": "Mood recorded successfully",
            "session_id": session_id
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": f"Error recording mood: {str(e)}"}), 500

@app.route('/api/resources', methods=['GET'])
def get_resources():
    category = request.args.get('category', None)
    
    conn = sqlite3.connect('mental_health_app.db')
    cursor = conn.cursor()
    
    if category:
        cursor.execute('SELECT * FROM resources WHERE category = ?', (category,))
    else:
        cursor.execute('SELECT * FROM resources')
    
    resources = cursor.fetchall()
    conn.close()
    
    resource_list = []
    for resource in resources:
        resource_list.append({
            "id": resource[0],
            "category": resource[1],
            "title": resource[2],
            "description": resource[3],
            "url": resource[4],
            "tags": resource[5].split(',') if resource[5] else []
        })
    
    return jsonify({"resources": resource_list})

# NEW FEATURE: Mood tracking visualization endpoint
@app.route('/api/mood/history', methods=['GET'])
def get_mood_history():
    session_id = request.cookies.get('session_id')
    if not session_id:
        return jsonify({"error": "No session found"}), 400
        
    try:
        conn = sqlite3.connect('mental_health_app.db')
        cursor = conn.cursor()
        
        # Get mood entries for the past 30 days
        cursor.execute("""
            SELECT mood_score, mood_description, timestamp
            FROM mood_entries
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT 30
        """, (session_id,))
        
        mood_data = []
        for row in cursor.fetchall():
            mood_data.append({
                "score": row[0],
                "description": row[1],
                "timestamp": row[2]
            })
            
        conn.close()
        
        return jsonify({
            "success": True,
            "mood_data": mood_data
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Error fetching mood history: {str(e)}"}), 500

# NEW FEATURE: Coping strategies endpoint
@app.route('/api/coping_strategies', methods=['GET'])
def get_coping_strategies():
    category = request.args.get('category', None)
    
    # Pre-defined coping strategies by category
    strategies = {
        "anxiety": [
            {"title": "4-7-8 Breathing", "description": "Inhale for 4 seconds, hold for 7, exhale for 8."},
            {"title": "Grounding Exercise", "description": "Name 5 things you can see, 4 you can touch, 3 you can hear, 2 you can smell, 1 you can taste."},
            {"title": "Progressive Muscle Relaxation", "description": "Tense and then relax each muscle group in your body."}
        ],
        "depression": [
            {"title": "Behavioral Activation", "description": "Do one small enjoyable activity today."},
            {"title": "Thought Challenge", "description": "Challenge negative thoughts with evidence."},
            {"title": "Small Goals", "description": "Set and accomplish one very small goal today."}
        ],
        "sleep": [
            {"title": "Sleep Hygiene", "description": "Keep a consistent sleep schedule and avoid screens before bed."},
            {"title": "Bedtime Routine", "description": "Create a relaxing pre-sleep routine to signal your body it's time to rest."},
            {"title": "Worry Journal", "description": "Write down worries before bed to clear your mind."}
        ]
    }
    
    if category and category in strategies:
        return jsonify({"strategies": strategies[category]})
    else:
        # Return all strategies if no category specified
        all_strategies = []
        for cat, strats in strategies.items():
            for strat in strats:
                strat["category"] = cat
                all_strategies.append(strat)
                
        return jsonify({"strategies": all_strategies})

# NEW FEATURE: Guided meditation/breathing exercises endpoint
@app.route('/api/exercises', methods=['GET'])
def get_exercises():
    exercise_type = request.args.get('type', 'breathing')
    
    exercises = {
        "breathing": [
            {
                "title": "Box Breathing",
                "description": "A simple technique to reduce stress and improve focus",
                "steps": [
                    "Inhale slowly through your nose for 4 seconds",
                    "Hold your breath for 4 seconds",
                    "Exhale slowly through your mouth for 4 seconds",
                    "Hold your breath for 4 seconds",
                    "Repeat for 5 cycles"
                ],
                "duration": "2 minutes"
            },
            {
                "title": "Diaphragmatic Breathing",
                "description": "Deep breathing technique to activate relaxation response",
                "steps": [
                    "Place one hand on your chest and the other on your stomach",
                    "Breathe in slowly through your nose, feeling your stomach expand",
                    "Exhale slowly through pursed lips, feeling your stomach fall",
                    "Repeat 10 times"
                ],
                "duration": "3 minutes"
            }
        ],
        "meditation": [
            {
                "title": "Body Scan Meditation",
                "description": "A mindfulness practice to release tension",
                "steps": [
                    "Find a comfortable position",
                    "Focus on your breath for a few moments",
                    "Gradually bring attention to different parts of your body",
                    "Notice any sensations without judgment",
                    "Release tension as you exhale"
                ],
                "duration": "5 minutes"
            },
            {
                "title": "Loving-Kindness Meditation",
                "description": "Practice to cultivate compassion for self and others",
                "steps": [
                    "Start by focusing on your breathing",
                    "Repeat phrases of kindness toward yourself",
                    "Extend these wishes to loved ones",
                    "Gradually extend to acquaintances and all beings"
                ],
                "duration": "7 minutes"
            }
        ]
    }
    
    if exercise_type in exercises:
        return jsonify({"exercises": exercises[exercise_type]})
    else:
        return jsonify({"exercises": exercises["breathing"]})  # Default to breathing exercises

# NEW FEATURE: Journal prompts endpoint
@app.route('/api/journal_prompts', methods=['GET'])
def get_journal_prompts():
    category = request.args.get('category', 'general')
    
    prompts = {
        "general": [
            "What are three things you're grateful for today?",
            "What's something that brought you joy recently?",
            "Write about a challenge you overcame and what you learned.",
            "What would you tell your younger self if you could?"
        ],
        "anxiety": [
            "What triggered your anxiety today?",
            "What thoughts come up when you feel anxious?",
            "What strategies have helped you manage anxiety in the past?",
            "What's one small step you can take toward managing your current worry?"
        ],
        "depression": [
            "What's one small thing you accomplished today?",
            "What activities used to bring you joy that you'd like to try again?",
            "What negative thought patterns do you notice when feeling down?",
            "What would a compassionate friend say to you right now?"
        ]
    }
    
    if category in prompts:
        # Return random selection of 3 prompts
        import random
        selected_prompts = random.sample(prompts[category], min(3, len(prompts[category])))
        return jsonify({"prompts": selected_prompts})
    else:
        return jsonify({"prompts": random.sample(prompts["general"], 3)})

# NEW FEATURE: Speech synthesis settings endpoint
@app.route('/api/speech/settings', methods=['GET', 'POST'])
def speech_settings():
    if request.method == 'POST':
        data = request.get_json()
        session_id = request.cookies.get('session_id', str(uuid.uuid4()))
        
        # Store speech settings in database
        try:
            conn = sqlite3.connect('mental_health_app.db')
            cursor = conn.cursor()
            
            # Check if table exists, create if not
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                session_id TEXT PRIMARY KEY,
                speech_enabled BOOLEAN DEFAULT TRUE,
                voice_name TEXT,
                voice_rate REAL DEFAULT 1.0,
                voice_pitch REAL DEFAULT 1.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Insert or update settings
            cursor.execute('''
            INSERT INTO user_settings (session_id, speech_enabled, voice_name, voice_rate, voice_pitch)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                speech_enabled = excluded.speech_enabled,
                voice_name = excluded.voice_name,
                voice_rate = excluded.voice_rate,
                voice_pitch = excluded.voice_pitch,
                updated_at = CURRENT_TIMESTAMP
            ''', (
                session_id,
                data.get('speechEnabled', True),
                data.get('voiceName', ''),
                data.get('voiceRate', 1.0),
                data.get('voicePitch', 1.0)
            ))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                "success": True,
                "message": "Speech settings updated",
                "session_id": session_id
            })
            
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Error updating speech settings: {str(e)}"
            }), 500
    
    else:  # GET request
        session_id = request.cookies.get('session_id')
        if not session_id:
            # Return default settings if no session
            return jsonify({
                "speechEnabled": True,
                "voiceRate": 1.0,
                "voicePitch": 1.0,
                "voiceName": ""
            })
        
        try:
            conn = sqlite3.connect('mental_health_app.db')
            cursor = conn.cursor()
            
            # Query settings
            cursor.execute('''
            SELECT speech_enabled, voice_name, voice_rate, voice_pitch 
            FROM user_settings 
            WHERE session_id = ?
            ''', (session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return jsonify({
                    "speechEnabled": bool(result[0]),
                    "voiceName": result[1],
                    "voiceRate": result[2],
                    "voicePitch": result[3]
                })
            else:
                # Return default settings if no record found
                return jsonify({
                    "speechEnabled": True,
                    "voiceRate": 1.0,
                    "voicePitch": 1.0,
                    "voiceName": ""
                })
                
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Error fetching speech settings: {str(e)}"
            }), 500

# Audio greeting endpoint
@app.route('/api/greeting', methods=['GET'])
def get_greeting():
    """Return a personalized greeting based on time of day or user history"""
    session_id = request.cookies.get('session_id')
    
    # Get time of day
    hour = datetime.datetime.now().hour
    
    # Base greeting on time of day
    if hour < 12:
        greeting = "Good morning! How are you feeling today?"
    elif hour < 18:
        greeting = "Good afternoon! How are you feeling today?"
    else:
        greeting = "Good evening! How are you feeling today?"
    
    # If we have session history, personalize more
    if session_id:
        try:
            conn = sqlite3.connect('mental_health_app.db')
            cursor = conn.cursor()
            
            # Get most recent mood entry
            cursor.execute('''
                SELECT mood_score, timestamp 
                FROM mood_entries 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (session_id,))
            
            mood_entry = cursor.fetchone()
            
            # Get user's name if we have it
            cursor.execute('''
                SELECT value FROM user_info 
                WHERE session_id = ? AND key = 'name'
                LIMIT 1
            ''', (session_id,))
            
            name_entry = cursor.fetchone()
            
            conn.close()
            
            # Personalize greeting with name if available
            if name_entry and name_entry[0]:
                greeting = greeting.replace("!", f", {name_entry[0]}!")
            
            # Reference their previous mood if available and recent (within last 24 hours)
            if mood_entry:
                mood_score = mood_entry[0]
                timestamp = datetime.datetime.strptime(mood_entry[1], '%Y-%m-%d %H:%M:%S')
                now = datetime.datetime.now()
                
                # If mood entry is from today or yesterday
                if (now - timestamp).days < 1:
                    if mood_score <= 3:
                        greeting += " I hope you're feeling better than you were earlier."
                    elif mood_score >= 8:
                        greeting += " I hope your day is still going well!"
        
        except Exception as e:
            print(f"Error personalizing greeting: {str(e)}")
    
    return jsonify({"greeting": greeting})

# NEW FEATURE: Community Support Groups
@app.route('/api/community_groups', methods=['GET'])
def get_community_groups():
    """Return available community support groups"""
    groups = [
        {
            "id": "1",
            "name": "Anxiety Support Circle",
            "description": "A safe space to share experiences and coping strategies for anxiety.",
            "meeting_times": "Tuesdays, 7-8pm EST",
            "virtual_link": "https://meet.example.com/anxiety-support",
            "category": "anxiety"
        },
        {
            "id": "2",
            "name": "Depression Recovery Group",
            "description": "Support for those experiencing depression or recovering.",
            "meeting_times": "Thursdays, 6-7pm EST",
            "virtual_link": "https://meet.example.com/depression-recovery",
            "category": "depression"
        },
        {
            "id": "3",
            "name": "Mindfulness Practice Community",
            "description": "Weekly guided meditations and mindfulness practice.",
            "meeting_times": "Saturdays, 10-11am EST",
            "virtual_link": "https://meet.example.com/mindfulness",
            "category": "mindfulness"
        },
        {
            "id": "4",
            "name": "Grief and Loss Support",
            "description": "A compassionate space for those experiencing grief or loss.",
            "meeting_times": "Wednesdays, 7-8:30pm EST",
            "virtual_link": "https://meet.example.com/grief-support",
            "category": "grief"
        }
    ]
    
    category = request.args.get('category', None)
    if category:
        filtered_groups = [g for g in groups if g["category"] == category]
        return jsonify({"groups": filtered_groups})
    
    return jsonify({"groups": groups})

# NEW FEATURE: User Progress Tracking
@app.route('/api/progress', methods=['GET'])
def get_user_progress():
    """Return user progress statistics"""
    session_id = request.cookies.get('session_id')
    if not session_id:
        return jsonify({"error": "No session found"}), 400
    
    try:
        conn = sqlite3.connect('mental_health_app.db')
        cursor = conn.cursor()
        
        # Get basic usage stats
        cursor.execute("SELECT COUNT(*) FROM chat_history WHERE session_id = ?", (session_id,))
        chat_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM mood_entries WHERE session_id = ?", (session_id,))
        mood_count = cursor.fetchone()[0]
        
        # Get average mood if available
        avg_mood = None
        mood_trend = "stable"
        if mood_count > 0:
            cursor.execute("SELECT AVG(mood_score) FROM mood_entries WHERE session_id = ?", 
                          (session_id,))
            avg_mood = cursor.fetchone()[0]
            
            # Get mood trend (comparing recent entries to older ones)
            if mood_count >= 4:
                cursor.execute("""
                    SELECT mood_score, timestamp FROM mood_entries 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC
                """, (session_id,))
                
                mood_entries = cursor.fetchall()
                recent_entries = mood_entries[:mood_count//2]
                older_entries = mood_entries[mood_count//2:]
                
                recent_avg = sum(entry[0] for entry in recent_entries) / len(recent_entries)
                older_avg = sum(entry[0] for entry in older_entries) / len(older_entries)
                
                if recent_avg - older_avg > 0.5:
                    mood_trend = "improving"
                elif older_avg - recent_avg > 0.5:
                    mood_trend = "declining"
        
        conn.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "chat_interactions": chat_count,
                "mood_entries": mood_count,
                "average_mood": avg_mood,
                "mood_trend": mood_trend,
                "streaks": {
                    "current_days": calculate_streak(session_id),
                    "longest_days": calculate_longest_streak(session_id)
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error fetching progress data: {str(e)}"
        }), 500

def calculate_streak(session_id):
    """Calculate current usage streak in days"""
    # Implementation would check for consecutive daily use
    # For demo purposes, returning a placeholder
    return 3

def calculate_longest_streak(session_id):
    """Calculate longest historical usage streak in days"""
    # Implementation would analyze historical usage patterns
    # For demo purposes, returning a placeholder 
    return 7
if __name__ == '__main__':
    app.run(debug=True, port=5002)