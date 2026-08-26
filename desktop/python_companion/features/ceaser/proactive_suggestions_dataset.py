"""
Proactive Suggestions Dataset
A curated dataset of contextual suggestions for the voice assistant
"""

# Context-aware proactive suggestions organized by command type
PROACTIVE_SUGGESTIONS_DATASET = {
    # AI/Knowledge Query Suggestions
    'ai_knowledge': [
        "Would you like me to explain more about this topic? Just say 'continue' or 'explain more'.",
        "I can dive deeper into this topic. Would you like more details?",
        "Would you like to know about related topics or applications?",
        "I can provide examples or practical applications. Interested?",
        "Would you like me to explain how this works in real-world scenarios?",
        "I can break this down into simpler terms or provide more advanced concepts. Which would you prefer?",
        "Would you like to explore similar topics or related concepts?",
        "I can give you a step-by-step explanation. Would that help?",
    ],
    
    # Quantum Computing Specific
    'quantum_computing': [
        "Would you like to know more about quantum computing applications or quantum algorithms?",
        "I can explain quantum supremacy, quantum error correction, or quantum gates. Which interests you?",
        "Would you like to learn about real-world quantum computers or quantum programming?",
        "I can discuss quantum cryptography or quantum machine learning. Interested?",
    ],
    
    # AI/Machine Learning Specific
    'ai_ml': [
        "Would you like me to explain more about AI applications, machine learning algorithms, or neural networks?",
        "I can discuss deep learning, reinforcement learning, or natural language processing. Which would you like?",
        "Would you like to know about AI ethics, AGI, or the future of artificial intelligence?",
        "I can explain how AI is used in healthcare, finance, or autonomous vehicles. Interested?",
    ],
    
    # Computer Science General
    'computer_science': [
        "Would you like to know more about computer science topics or related technologies?",
        "I can explain algorithms, data structures, or software engineering concepts. Which interests you?",
        "Would you like to learn about programming languages, operating systems, or networking?",
        "I can discuss cybersecurity, cloud computing, or distributed systems. Interested?",
    ],
    
    # Task/Productivity Suggestions
    'task_productivity': [
        "I can help you manage your tasks better. Would you like me to create a task list or set up reminders?",
        "Would you like me to prioritize your tasks or create a schedule?",
        "I can help you break down complex tasks into smaller steps. Interested?",
        "Would you like me to set up recurring tasks or calendar reminders?",
        "I can help you track your productivity or analyze your task completion patterns.",
    ],
    
    # System/Device Control Suggestions
    'system_control': [
        "I can help you control more system functions. Would you like me to show you available commands?",
        "Would you like to adjust system settings, manage files, or control applications?",
        "I can help you automate repetitive system tasks. Interested?",
        "Would you like me to monitor system performance or optimize settings?",
    ],
    
    # Weather Suggestions
    'weather': [
        "I can check weather for multiple locations or provide extended forecasts. Would you like that?",
        "Would you like hourly forecasts, severe weather alerts, or weather comparisons?",
        "I can provide weather-based recommendations for outdoor activities. Interested?",
        "Would you like me to track weather patterns or set up weather alerts?",
    ],
    
    # News Suggestions
    'news': [
        "I can get news from specific categories or sources. Which would you like?",
        "Would you like tech news, world news, business updates, or science headlines?",
        "I can provide news summaries or detailed articles. Which do you prefer?",
        "Would you like me to track specific topics or create a personalized news feed?",
    ],
    
    # Music/Media Suggestions
    'music_media': [
        "I can help you discover new music or create playlists. Would you like that?",
        "Would you like me to play music based on your mood, activity, or preferences?",
        "I can help you find similar artists or explore new genres. Interested?",
        "Would you like me to create a workout playlist or background music for focus?",
    ],
    
    # Learning Suggestions
    'learning': [
        "I can help you track your learning progress or create custom lessons. Interested?",
        "Would you like to practice vocabulary, take quizzes, or review previous lessons?",
        "I can create flashcards, spaced repetition schedules, or learning goals. Which would help?",
        "Would you like me to adapt lessons based on your learning pace or difficulty?",
    ],
    
    # Time-Based Suggestions
    'morning': [
        "Good morning! Would you like me to check your schedule, weather, or daily tasks?",
        "I can help you start your day right. Would you like a productivity boost or morning routine suggestions?",
        "Would you like me to review your calendar, prioritize tasks, or check important reminders?",
    ],
    
    'afternoon': [
        "Afternoon check-in! How are you doing? I can help you stay productive or take a well-deserved break.",
        "Would you like me to review your progress, suggest a break, or help with upcoming tasks?",
        "I can help you stay focused or recharge. Which would you prefer?",
    ],
    
    'evening': [
        "Evening time! Ready to wrap up? I can help you organize tomorrow's tasks or perform system maintenance.",
        "Would you like me to review your day, plan tomorrow, or help you unwind?",
        "I can help you prepare for tomorrow or wrap up today's work. Which would you like?",
    ],
    
    # System Health Suggestions
    'system_health': [
        "I notice your system memory usage is high. Would you like me to suggest ways to optimize it?",
        "Your system could benefit from maintenance. Would you like me to help optimize performance?",
        "I can help you free up disk space, close unused apps, or clear temporary files. Interested?",
        "Would you like me to analyze system resources and suggest improvements?",
    ],
    
    # Conversation Flow Suggestions
    'conversation_break': [
        "We've been talking for a while. Would you like to take a break or continue with something else?",
        "You've been very productive! Would you like to pause or explore other topics?",
        "I've enjoyed our conversation. Would you like to continue or wrap up?",
    ],
    
    # General Helpful Suggestions
    'general_help': [
        "Is there anything else I can help you with?",
        "Would you like me to show you available commands or features?",
        "I'm here to help. What would you like to do next?",
        "Would you like to explore more features or try something new?",
    ],
}

def get_suggestion_for_context(command_text: str, response: str = "", conversation_count: int = 0) -> str:
    """
    Get a contextual proactive suggestion based on the command and response
    
    Args:
        command_text: The user's command
        response: The assistant's response
        conversation_count: Number of commands in current conversation
        
    Returns:
        A relevant proactive suggestion string
    """
    import random
    
    command_lower = command_text.lower()
    response_lower = response.lower() if response else ""
    
    # Determine context category
    category = None
    
    # AI/Knowledge queries
    if any(word in command_lower for word in ['what is', 'what are', 'explain', 'tell me about', 'how', 'why', 'when', 'where', 'who', 'which', 'define']):
        if 'quantum' in command_lower or 'quantum' in response_lower:
            category = 'quantum_computing'
        elif 'ai' in command_lower or 'artificial intelligence' in command_lower or 'machine learning' in command_lower or 'neural' in command_lower:
            category = 'ai_ml'
        elif 'computing' in command_lower or 'computer' in command_lower or 'programming' in command_lower:
            category = 'computer_science'
        else:
            category = 'ai_knowledge'
    
    # Task/Productivity
    elif any(word in command_lower for word in ['task', 'reminder', 'schedule', 'calendar', 'todo', 'todo list']):
        category = 'task_productivity'
    
    # System/Device
    elif any(word in command_lower for word in ['open', 'close', 'volume', 'brightness', 'screenshot', 'system', 'app']):
        category = 'system_control'
    
    # Weather
    elif 'weather' in command_lower:
        category = 'weather'
    
    # News
    elif 'news' in command_lower:
        category = 'news'
    
    # Music/Media
    elif any(word in command_lower for word in ['play', 'music', 'youtube', 'spotify', 'song', 'album']):
        category = 'music_media'
    
    # Learning
    elif any(word in command_lower for word in ['learn', 'lesson', 'practice', 'vocabulary', 'study']):
        category = 'learning'
    
    # Time-based suggestions
    from datetime import datetime
    current_hour = datetime.now().hour
    if 6 <= current_hour <= 11:
        category = 'morning'
    elif 12 <= current_hour <= 17:
        category = 'afternoon'
    elif 18 <= current_hour <= 23:
        category = 'evening'
    
    # System health check (if category not set yet)
    if not category:
        try:
            import psutil
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                category = 'system_health'
        except:
            pass
    
    # Conversation break suggestion
    if conversation_count >= 3 and not category:
        category = 'conversation_break'
    
    # Fallback to general help
    if not category:
        category = 'general_help'
    
    # Get random suggestion from category
    if category in PROACTIVE_SUGGESTIONS_DATASET:
        suggestions = PROACTIVE_SUGGESTIONS_DATASET[category]
        return random.choice(suggestions)
    
    return ""

def get_all_suggestions_for_category(category: str) -> list:
    """Get all suggestions for a specific category"""
    return PROACTIVE_SUGGESTIONS_DATASET.get(category, [])

def add_custom_suggestion(category: str, suggestion: str):
    """Add a custom suggestion to a category"""
    if category not in PROACTIVE_SUGGESTIONS_DATASET:
        PROACTIVE_SUGGESTIONS_DATASET[category] = []
    PROACTIVE_SUGGESTIONS_DATASET[category].append(suggestion)

def get_suggestion_count() -> dict:
    """Get count of suggestions per category"""
    return {category: len(suggestions) for category, suggestions in PROACTIVE_SUGGESTIONS_DATASET.items()}

