import os
from flask import Flask, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
PORT = os.getenv('PORT', 8000)
DEBUG = os.getenv('DEBUG', False)

# Load environment variables
load_dotenv()

DAILY_PROMPT = None

class PromptGenerator:
    def __init__(self, api_client):
        """
        Initialize PromptGenerator with OpenAI client.
        """
        self.client = api_client

        # Prompts for generating creative photographic prompts
        self.system_prompt = '''
Generate a single, precise photographic challenge that provides a unique directional prompt for personal photography. Each prompt must:
- Be clear, simple, and concise
- Encourage users to have fun.
- Give specific directions
- Be one sentence long (~15 words)
- Be accessible and easy to do for most people
- THE SUBJECT OF THE PHOTO SHOULD BE THE USER
'''
        self.user_prompt = '''
Generate a creative photographic direction that meets the requirements.
'''

        # Prompts for generating photo tips
        self.tip_system_prompt = '''
Generate a single, clear, and concise photo tip for photographers. Each tip must:
- Be practical and actionable
- Be one sentence long
- Cover a general aspect of photography
- Be helpful for photographers of all levels
- Be something that people aren't likely to know
'''
        self.tip_user_prompt = '''
Provide a helpful photo-taking tip that photographers can apply in their daily practice.
'''

    # --- Prompt Generation Methods ---
    def generate_creative_prompt(self):
        """Generate a creative prompt using OpenAI API."""
        try:
            prompt_generation_request = self.client.chat.completions.create(
                model="donna_alfonso_damian",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": self.user_prompt}
                ]
            )

            return prompt_generation_request.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating creative prompt: {e}")
            return None

    def generate_creative_tip(self):
        """Generate a creative photo tip using OpenAI API."""
        try:
            tip_generation_request = self.client.chat.completions.create(
                model="donna_alfonso_damian",
                messages=[
                    {"role": "system", "content": self.tip_system_prompt},
                    {"role": "user", "content": self.tip_user_prompt}
                ]
            )

            return tip_generation_request.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating creative tip: {e}")
            return None
    def generate_daily_prompt(self):
        """Generate a new daily prompt and store it in global variable."""
        global DAILY_PROMPT
        DAILY_PROMPT = self.generate_creative_prompt()
def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    CORS(app)

    # Omnistack OpenAI Client
    omnistack_client = OpenAI(
        base_url="https://api.omnistack.sh/openai/v1", 
        api_key=os.getenv('OMNISTACK_API_KEY'),
    )

    # Initialize PromptGenerator
    prompt_generator = PromptGenerator(omnistack_client)

    @app.route('/prompt/daily', methods=['GET'])
    def daily_prompt():
        """Route to retrieve a new daily prompt."""
        if not DAILY_PROMPT:
            prompt_generator.generate_daily_prompt()
        prompt = DAILY_PROMPT
        if not prompt:
            prompt = "Capture the beauty of a sunset with a friend."
        
        return jsonify({'prompt': prompt})

    @app.route('/prompt/random', methods=['GET'])
    def random_prompt():
        """Route to generate a random prompt."""
        try:
            random_prompt = prompt_generator.generate_creative_prompt()
            if random_prompt is None:
                # Provide a default prompt if generation fails
                random_prompt = "Capture the beauty of a sunset."
            return jsonify({'random_prompt': random_prompt})
        except Exception as e:
            return jsonify({'message': 'Error generating random prompt', 'error': str(e)}), 500

    @app.route('/prompt/tip', methods=['GET'])
    def photo_tip():
        """Route to retrieve a new photo tip."""
        tip = prompt_generator.generate_creative_tip()
        if tip is None:
            # Provide a default tip if generation fails
            tip = "Remember to check your camera settings before shooting."
        return jsonify({'tip': tip})

    # Setup scheduler to generate daily prompt at midnight
    scheduler = BackgroundScheduler()
    scheduler.add_job(prompt_generator.generate_daily_prompt, 'cron', hour=0, minute=0)
    scheduler.start()
    return app

# Application entry point
app = create_app()

if __name__ == '__main__':
    app.run(port=PORT, debug=DEBUG, host="0.0.0.0")
