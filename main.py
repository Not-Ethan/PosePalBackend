import os
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

class PromptGenerator:
    def __init__(self, api_client, prompt_file='daily_prompt.json'):
        """
        Initialize PromptGenerator with OpenAI client and prompt file path.
        
        :param api_client: OpenAI-compatible client for generating prompts
        :param prompt_file: Path to the JSON file storing daily prompts
        """
        self.client = api_client
        self.prompt_file = prompt_file

    def load_prompts(self):
        """
        Load existing daily prompts from file.
        
        :return: Dictionary of stored prompts
        """
        try:
            with open(self.prompt_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_prompts(self, prompts):
        """
        Save prompts to JSON file.
        
        :param prompts: Dictionary of prompts to save
        """
        with open(self.prompt_file, 'w') as f:
            json.dump(prompts, f, indent=2)

    def generate_prompt(self, prompt_type='daily', num_prompts=1):
        """
        Generate prompt(s) using OpenAI client.
        
        :param prompt_type: Type of prompt generation (daily or random)
        :param num_prompts: Number of prompts to generate
        :return: Generated prompt(s)
        """
        try:
            # Determine system and user messages based on prompt type
            system_messages = {
                'daily': "Generate a unique, fun photo pose suggestion.",
                'random': f"Generate {num_prompts} unique, fun photo pose suggestions."
            }
            
            user_messages = {
                'daily': "Suggest a creative and engaging photo pose.",
                'random': "Suggest some creative and engaging photo poses."
            }
            
            # Create prompt generation request
            random_prompts_response = self.client.chat.completions.create(
                model="donna_alfonso_damian",
                messages=[
                    {"role": "system", "content": system_messages.get(prompt_type, system_messages['daily'])},
                    {"role": "user", "content": user_messages.get(prompt_type, user_messages['daily'])}
                ]
            )
            
            # Extract and process prompts
            prompts = [
                choice.message.content 
                for choice in random_prompts_response.choices 
                if choice.message.content
            ]
            
            # For daily prompt, save to file
            if prompt_type == 'daily':
                today = datetime.now().strftime('%Y-%m-%d')
                stored_prompts = self.load_prompts()
                stored_prompts[today] = prompts[0]
                
                # Prune old prompts (keep last 30 days)
                cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                stored_prompts = {k: v for k, v in stored_prompts.items() if k >= cutoff_date}
                
                self.save_prompts(stored_prompts)
                print(f"Generated daily prompt for {today}: {prompts[0]}")
            
            return prompts[0] if prompt_type == 'daily' else prompts
        
        except Exception as e:
            print(f"Error generating {prompt_type} prompt: {e}")
            return None

    def get_daily_prompt(self):
        """
        Retrieve today's prompt from the stored prompts file.
        
        :return: Dictionary with date and prompt
        """
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            with open(self.prompt_file, 'r') as f:
                prompt = json.load(f).get(today)
                return {'date': today, 'prompt': prompt}
        except FileNotFoundError:
            return "Daily prompt file not found"
        except json.JSONDecodeError:
            return "Error reading daily prompt file"

def create_app():
    """
    Create and configure Flask application.
    
    :return: Configured Flask app
    """
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
        """Route to generate random prompts."""
        try:
            random_prompts = prompt_generator.generate_prompt(prompt_type='random', num_prompts=3)
            return jsonify({'random_prompts': random_prompts})
        except Exception as e:
            return jsonify({'message': 'Error generating random prompts', 'error': str(e)}), 500

    # Setup scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: prompt_generator.generate_prompt(prompt_type='daily'), 'cron', hour=0, minute=0)
    scheduler.start()

    # Create daily prompt file if it doesn't exist
    if not os.path.exists(prompt_generator.prompt_file):
        prompt_generator.generate_prompt(prompt_type='daily')

    return app

# Application entry point
app = create_app()

if __name__ == '__main__':
    app.run(port=8000, debug=True)