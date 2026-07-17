import os
import sys
import threading
import re
import joblib
from scipy.sparse import hstack
import scipy.sparse as sp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, 'Machine_Learning', 'models')
sys.path.insert(0, os.path.join(BASE_DIR, 'Machine_Learning'))
from description_templates import project_description, task_description, fallback_description

# Load models safely (lazy loading or global load)
task_classifier = None
priority_classifier = None
duration_predictor = None
duration_tfidf = None
le_cat = None
le_pri = None
_model_lock = threading.Lock()

def load_models():
    global task_classifier, priority_classifier, duration_predictor, duration_tfidf, le_cat, le_pri
    if task_classifier is None:
        with _model_lock:
            if task_classifier is None:
                try:
                    task_classifier = joblib.load(os.path.join(MODELS_DIR, 'task_classifier.pkl'))
                    priority_classifier = joblib.load(os.path.join(MODELS_DIR, 'priority_classifier.pkl'))
                    duration_predictor = joblib.load(os.path.join(MODELS_DIR, 'duration_predictor.pkl'))
                    duration_tfidf = joblib.load(os.path.join(MODELS_DIR, 'duration_tfidf.pkl'))
                    le_cat = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_category.pkl'))
                    le_pri = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_priority.pkl'))
                except Exception as e:
                    print(f"Error loading models: {e}")

def _sanitize(text: str, max_len: int = 500) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if not text:
        return ""
    text = re.sub(r'[^a-z0-9\s\.\-\/]', '', text.lower())
    return text[:max_len]

def predict_project(text: str) -> dict:
    load_models()
    
    if not task_classifier:
        return {
            'category': 'Task',
            'priority': 'Medium',
            'duration_days': 10,
            'suggested_description': fallback_description('project')
        }
        
    text_lower = _sanitize(text)
    cat = task_classifier.predict([text_lower])[0]
    pri = priority_classifier.predict([text_lower])[0]
    
    text_tfidf = duration_tfidf.transform([text_lower])
    cat_enc = le_cat.transform([cat])[0]
    pri_enc = le_pri.transform([pri])[0]
    
    extra = sp.csr_matrix([[cat_enc, pri_enc]])
    combined = hstack([text_tfidf, extra])
    
    dur = max(10, int(round(duration_predictor.predict(combined)[0])))
    
    suggested_description = project_description(cat, text, pri, dur)
    
    return {
        'category': cat,
        'priority': pri,
        'duration_days': dur,
        'suggested_description': suggested_description
    }

def predict_task(text: str) -> dict:
    load_models()
    
    if not task_classifier:
        return {
            'category': 'Task',
            'priority': 'Medium',
            'duration_days': 10,
            'suggested_description': fallback_description('task')
        }
        
    text_lower = _sanitize(text)
    
    cat = task_classifier.predict([text_lower])[0]
    pri = priority_classifier.predict([text_lower])[0]
    
    text_tfidf = duration_tfidf.transform([text_lower])
    cat_enc = le_cat.transform([cat])[0]
    pri_enc = le_pri.transform([pri])[0]
    
    extra = sp.csr_matrix([[cat_enc, pri_enc]])
    combined = hstack([text_tfidf, extra])
    
    dur = max(1, int(round(duration_predictor.predict(combined)[0])))
    
    suggested_description = task_description(cat, text, pri, dur)
    
    return {
        'category': cat,
        'priority': pri,
        'duration_days': dur,
        'suggested_description': suggested_description
    }
