import os
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

PORT = os.getenv('PORT', 8000)
DEBUG = os.getenv('DEBUG', False)

# Load environment variables
load_dotenv()

class PromptGenerator:
    def __init__(self, api_client, prompt_file='daily_prompt.json', prompt_template='prompt.txt'):
        """
        Initialize PromptGenerator with OpenAI client, prompt file paths.
        """
        self.client = api_client
        self.prompt_file = prompt_file
        self.prompt_template = prompt_template
        self.system_prompt = '''
Generate a single, precise photographic challenge that provides a unique directional prompt for personal photography. Each prompt must:
- Be clear, simple, and concise
- Encourage users to have fun.
- Give specific directions
- Be one sentence long (~10 words)
- Be accessible and easy to do for most people
'''
        self.user_prompt = '''
Generate a creative photographic direction that meets the requirements.'''

    def load_prompts(self):
        """Load existing daily prompts from file."""
        try:
            with open(self.prompt_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_prompts(self, prompts):
        """Save prompts to JSON file."""
        with open(self.prompt_file, 'w') as f:
            json.dump(prompts, f, indent=2)

    def generate_creative_prompt(self):
        """Generate a creative prompt using loaded template."""
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

    def generate_daily_prompt(self):
        """Generate and save today's prompt."""
        today = datetime.now().strftime('%Y-%m-%d')
        prompt = self.generate_creative_prompt()
        
        if prompt:
            # Load existing prompts
            prompts = self.load_prompts()
            
            # Add today's prompt
            prompts[today] = prompt
            
            # Prune old prompts (keep last 30 days)
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            prompts = {k: v for k, v in prompts.items() if k >= cutoff_date}
            
            # Save updated prompts
            self.save_prompts(prompts)
            print(f"Generated daily prompt for {today}: {prompt}")
            
        return prompt

    def get_daily_prompt(self):
        """Retrieve today's prompt from the stored prompts file."""
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            with open(self.prompt_file, 'r') as f:
                prompts = json.load(f)
                
                # If no prompt for today, generate one
                if today not in prompts:
                    prompt = self.generate_daily_prompt()
                else:
                    prompt = prompts[today]
                
                return {'date': today, 'prompt': prompt}
        except (FileNotFoundError, json.JSONDecodeError):
            # Generate prompt if file doesn't exist or is invalid
            prompt = self.generate_daily_prompt()
            return {'date': today, 'prompt': prompt if prompt else 'This would be a default random prompt.'}

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
        """Route to retrieve the daily prompt."""
        daily_prompt = prompt_generator.get_daily_prompt()
        return jsonify(daily_prompt)

    @app.route('/prompt/random', methods=['GET'])
    def random_prompt():
        """Route to generate a random prompt."""
        try:
            random_prompt = prompt_generator.generate_creative_prompt()
            return jsonify({'random_prompt': random_prompt})
        except Exception as e:
            return jsonify({'message': 'Error generating random prompt', 'error': str(e)}), 500

    # Setup scheduler to generate daily prompt at midnight
    scheduler = BackgroundScheduler()
    scheduler.add_job(prompt_generator.generate_daily_prompt, 'cron', hour=0, minute=0)
    scheduler.start()

    return app

# Application entry point
app = create_app()

if __name__ == '__main__':
    app.run(port=PORT, debug=DEBUG, host="0.0.0.0")