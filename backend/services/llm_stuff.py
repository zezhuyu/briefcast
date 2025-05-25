
import torch
import gc
import re
import inspect
import soundfile as sf
from pydub import AudioSegment
from io import BytesIO
import numpy as np
import warnings
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constant.labels import general_labels, sub_labels
from constant.prompt import SYSTEMP_PROMPT_SUMMARY
from dotenv import load_dotenv


# Load environment variables
load_dotenv()
warnings.filterwarnings('ignore')


OLLAMA = os.getenv('OLLAMA', True)
MODEL = os.getenv('MODEL', "llama3.1")
LLM_API = os.getenv('LLM_API', "http://localhost:11434/v1")
EMBEDDING = os.getenv('EMBEDDING', "BAAI/bge-base-en-v1.5")
KEYBERT_MODEL = os.getenv('KEYBERT_MODEL', "all-MiniLM-L6-v2")
CLASSIFIER_MODEL = os.getenv('CLASSIFIER_MODEL', "facebook/bart-large-mnli")
SUMMARIZER_MODEL = os.getenv('SUMMARIZER_MODEL', "facebook/bart-base")
AUDIO_MODEL = os.getenv('AUDIO_MODEL', "hexgrad/Kokoro-82M")
IMAGE_MODEL = os.getenv('IMAGE_MODEL', "stabilityai/sdxl-turbo")
EMBEDDING_SERVER = os.getenv('EMBEDDING_SERVER', "localhost:50051")

if not OLLAMA:
    from accelerate import Accelerator
    from transformers import pipeline, BitsAndBytesConfig
    import torch

    accelerator = Accelerator()
    llm = pipeline(
        "text-generation",
        model=MODEL,
        model_kwargs={"torch_dtype": torch.bfloat16},
        device_map="cuda",
        max_new_tokens=8126,
        temperature=1,
    )
else:
    from openai import OpenAI
    llm = OpenAI(base_url = LLM_API, api_key='ollama')

def get_main_module_name():
    main = sys.modules.get('__main__')
    if not main:
        return None
    if hasattr(main, '__package__') and main.__package__:
        return main.__package__ + '.' + os.path.splitext(os.path.basename(main.__file__))[0]
    elif hasattr(main, '__file__'):
        return os.path.splitext(os.path.basename(main.__file__))[0]
    else:
        return None

if get_main_module_name() == "news_crawler":
    import torch
    from sentence_transformers import SentenceTransformer
    from transformers import pipeline
    from keybert import KeyBERT

    embed_model = SentenceTransformer(EMBEDDING, device="cuda")
    model = SentenceTransformer(KEYBERT_MODEL, device="cuda")
    classifier = pipeline("zero-shot-classification", model=CLASSIFIER_MODEL, device="cuda")
    summarizer = pipeline("summarization", model=SUMMARIZER_MODEL, device="cuda")
    kw_model = KeyBERT(model)

if get_main_module_name() == "app":
    import grpc
    from comp.embedding_pb2 import TextRequest
    from comp.embedding_pb2_grpc import EmbedServiceStub

    channel = grpc.insecure_channel(EMBEDDING_SERVER)
    stub = EmbedServiceStub(channel)

    # embed_model = SentenceTransformer(EMBEDDING, device="cuda")
    # audio_pipeline = KPipeline(repo_id=AUDIO_MODEL, lang_code='a', device="cuda")
    # pipe = AutoPipelineForText2Image.from_pretrained(IMAGE_MODEL, variant="fp16", torch_dtype=torch.float16, low_cpu_mem_usage=True).to("cuda")

if get_main_module_name() == "async_generator":
    import torch
    from kokoro import KPipeline
    from diffusers import AutoPipelineForText2Image
    audio_pipeline = KPipeline(repo_id=AUDIO_MODEL, lang_code='a', device="cuda")
    pipe = AutoPipelineForText2Image.from_pretrained(IMAGE_MODEL, variant="fp16", torch_dtype=torch.float16, low_cpu_mem_usage=True).to("cuda")


# import torch
# from sentence_transformers import SentenceTransformer
# from transformers import pipeline
# from keybert import KeyBERT

# embed_model = SentenceTransformer(EMBEDDING, device="cuda")
# model = SentenceTransformer(KEYBERT_MODEL, device="cuda")
# classifier = pipeline("zero-shot-classification", model=CLASSIFIER_MODEL, device="cuda")
# summarizer = pipeline("summarization", model=SUMMARIZER_MODEL, device="cuda")
# kw_model = KeyBERT(model)


gc.collect()
torch.cuda.empty_cache()

def format_timestamp(seconds):
    """Convert seconds to LRC timestamp format [mm:ss.xx]"""
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 100)
    return f"[{minutes:02}:{sec:02}.{millis:02}]"

def create_audio(audio_text, voice='bm_george', split_pattern=r'\s*,\s*'):
    torch.cuda.empty_cache()
    generator = audio_pipeline(
        audio_text, voice=voice, # 'af_heart', 'af_bella', 'bm_george', 'am_adam', 'af_nicole'
        speed=1, split_pattern=split_pattern
    )
    start_time = 0.0
    combined_audio = AudioSegment.silent(duration=0)
    lyric = []
    
    for i, (gs, ps, audio) in enumerate(generator):
        duration = len(audio) / 24000  
        timestamp = format_timestamp(start_time)
        gs = gs.replace("\n", " ").rstrip(" \t\n").rstrip(" \n\t").rstrip(".,!?")
        lyric.append(f"{timestamp}{gs}")
        start_time += duration  
        audio_np = audio.cpu().numpy()
        
        if audio_np.dtype == np.float32:
            audio_np = np.int16(audio_np * 32767)
        
        segment = AudioSegment(
            data=audio_np.tobytes(), 
            sample_width=audio_np.dtype.itemsize, 
            frame_rate=24000, 
            channels=1
        )

        segment = segment.set_frame_rate(48000)
        segment = segment.set_channels(2)
        
        combined_audio += segment

    audio_buffer = BytesIO()
    combined_audio.export(audio_buffer, format="wav")
    audio_buffer.seek(0)
    torch.cuda.empty_cache()
    return audio_buffer, lyric

def create_image(text):
    torch.cuda.empty_cache()
    image = pipe(prompt=text, num_inference_steps=5, guidance_scale=0.0).images[0]
    torch.cuda.empty_cache()
    return image


def create_label(article):
    torch.cuda.empty_cache()
    result = classifier(article, candidate_labels=general_labels)
    general_label = result['labels'][0]

    sub_label_result = classifier(article, candidate_labels=sub_labels.get(general_label, []))
    sub_label = sub_label_result['labels'][0]
    torch.cuda.empty_cache()
    return general_label, sub_label

def create_summary(article):
    if article == "":
        return ""
    if len(article.split()) > 300:
        messages = [
            {"role": "system", "content": SYSTEMP_PROMPT_SUMMARY},
            {"role": "user", "content": article},
        ]
        return call_llm(messages)
    else:
        summary = summarizer(article, max_length=50, min_length=25, do_sample=False)
        return summary[0]['summary_text']

def create_keywords(article):
    torch.cuda.empty_cache()
    key_phrases = kw_model.extract_keywords(article, keyphrase_ngram_range=(1, 2), top_n=3)
    keywords = [phrase[0] for phrase in key_phrases]
    torch.cuda.empty_cache()
    return keywords

def call_llm(messages):
    if OLLAMA:
        try:
            outputs = llm.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=8126,
                temperature=1,
            )
            return outputs.choices[0].message.content
        except Exception as e:
            print(e)
            return None
    else:
        try:
            torch.cuda.empty_cache()
            outputs = llm(
                messages,
                max_new_tokens=8126,
                temperature=1,
            )
            torch.cuda.empty_cache()
            return outputs[0]["generated_text"][-1]['content']
        except RuntimeError as e:
            if "out of memory" in str(e):
                print("CUDA out of memory error")
                torch.cuda.empty_cache()
                raise e

def create_embedding(text):
    if get_main_module_name() == "app":
        request = TextRequest(text=text)
        response = stub.GetEmbedding(request)
        return np.array(response.values)
    else:
        torch.cuda.empty_cache()
        embedding = embed_model.encode([text])[0]
        torch.cuda.empty_cache()
        return embedding
