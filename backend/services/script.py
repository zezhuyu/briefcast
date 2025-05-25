from tqdm.notebook import tqdm
import warnings
import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm_stuff import call_llm
from constant.prompt import SYSTEMP_PROMPT_WRITER, SYSTEMP_PROMPT_REWRITER_2, SYSTEMP_PROMPT_TRANSITION, SYSTEMP_PROMPT_WEATHER

warnings.filterwarnings('ignore')


output_dir = './resources'
os.makedirs(output_dir, exist_ok=True)

# Function to read a file and return its content
def read_file_to_string(filename):
    # Try UTF-8 first (most common encoding for text files)
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except UnicodeDecodeError:
        # If UTF-8 fails, try with other common encodings
        encodings = ['latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                with open(filename, 'r', encoding=encoding) as file:
                    content = file.read()
                print(f"Successfully read file using {encoding} encoding.")
                return content
            except Exception as e:
                print(f"Failed to read file with {encoding} encoding: {e}")
    return None



def create_podcast(input_file=None, input_text=None, output_file=None):
    if not input_file and (not input_text or input_text == ""):
        raise Exception("input must not be empty")

    if input_file:
        input_text = read_file_to_string(input_file)
        
    messages = [
        {"role": "system", "content": SYSTEMP_PROMPT_WRITER},
        {"role": "user", "content": input_text},
    ]
    
    
    save_string_pkl = call_llm(messages)

    if output_file:
        with open(os.path.join(output_dir, output_file), 'w', encoding='utf-8') as file:
            file.write(save_string_pkl)

    return save_string_pkl

def rewrite_podcast(input_text, output_file=None):
    if not input_text or input_text == "":
        raise Exception("input must not be empty")

    messages = [
        {"role": "system", "content": SYSTEMP_PROMPT_REWRITER_2},
        {"role": "user", "content": input_text},
    ]

    save_string_rewrite = call_llm(messages)
    
    if output_file:
        with open(os.path.join(output_dir, output_file), 'w', encoding='utf-8') as file:
            file.write(save_string_rewrite)
            
    return save_string_rewrite

def create_transition(script1, script2):
    if script1 == "" or script2 == "" or script1 == script2:
        raise Exception("transition script must not be empty")

    messages = [
        {"role": "system", "content": SYSTEMP_PROMPT_TRANSITION},
        {"role": "user", "content": script1},
        {"role": "user", "content": script2},
        {"role": "assistant", "content": "Please create a smooth transition between the two news scripts provided."},  # Model's role
    ]

    transition = call_llm(messages)

    return transition

def create_weather_forecast(weather):
    if weather == "":
        raise Exception("weather script must not be empty")

    messages = [
        {"role": "system", "content": SYSTEMP_PROMPT_WEATHER},
        {"role": "user", "content": weather},
    ]

    forecast = call_llm(messages)

    return forecast

    
    