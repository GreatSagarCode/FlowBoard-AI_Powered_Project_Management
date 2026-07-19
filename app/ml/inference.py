import os
import threading
import re
import joblib
from scipy.sparse import hstack
import scipy.sparse as sp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, 'Machine_Learning', 'models')

_description_templates = None
_description_templates_lock = threading.Lock()

def _load_description_templates():
    global _description_templates
    if _description_templates is not None:
        return
    with _description_templates_lock:
        if _description_templates is not None:
            return
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "description_templates",
                os.path.join(BASE_DIR, 'Machine_Learning', 'description_templates.py')
            )
            if spec is None:
                return
            dt = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dt)
            _description_templates = dt
        except Exception:
            pass

_PREPROC_CONFIG = None

def _load_preproc_config():
    global _PREPROC_CONFIG
    if _PREPROC_CONFIG is not None:
        return
    config_path = os.path.join(MODELS_DIR, 'preprocessing_config.pkl')
    if os.path.exists(config_path):
        try:
            _PREPROC_CONFIG = joblib.load(config_path)
        except Exception:
            pass

def _sanitize(text: str, max_len: int = 500) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if not text:
        return ""
    _load_preproc_config()
    if _PREPROC_CONFIG and 'regex' in _PREPROC_CONFIG:
        regex = _PREPROC_CONFIG['regex']
    else:
        regex = r'[^a-z0-9\s\.\-\/]'
    if _PREPROC_CONFIG and 'max_len' in _PREPROC_CONFIG:
        max_len = _PREPROC_CONFIG['max_len']
    text = re.sub(regex, '', text.lower())
    return text[:max_len]

task_classifier = None
priority_classifier = None
duration_predictor = None
duration_tfidf = None
le_cat = None
le_pri = None
_model_lock = threading.Lock()
_models_loaded = False

def load_models():
    global task_classifier, priority_classifier, duration_predictor, duration_tfidf, le_cat, le_pri, _models_loaded
    if _models_loaded:
        return
    with _model_lock:
        if _models_loaded:
            return
        try:
            task_classifier = joblib.load(os.path.join(MODELS_DIR, 'task_classifier.pkl'))
            priority_classifier = joblib.load(os.path.join(MODELS_DIR, 'priority_classifier.pkl'))
            duration_predictor = joblib.load(os.path.join(MODELS_DIR, 'duration_predictor.pkl'))
            duration_tfidf = joblib.load(os.path.join(MODELS_DIR, 'duration_tfidf.pkl'))
            le_cat = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_category.pkl'))
            le_pri = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_priority.pkl'))
            _models_loaded = True
        except Exception as e:
            print(f"Error loading models: {e}")

def _fallback(kind):
    _load_description_templates()
    desc = _description_templates.fallback_description(kind) if _description_templates else 'Please provide more details.'
    return {
        'category': 'Task',
        'priority': 'Medium',
        'duration_days': 10,
        'suggested_description': desc
    }

def predict_project(text: str) -> dict:
    try:
        load_models()
        _load_description_templates()

        if not _models_loaded:
            return _fallback('project')

        text_lower = _sanitize(text)
        cat = task_classifier.predict([text_lower])[0]
        pri = priority_classifier.predict([text_lower])[0]

        text_tfidf = duration_tfidf.transform([text_lower])
        cat_enc = le_cat.transform([cat])[0]
        pri_enc = le_pri.transform([pri])[0]

        extra = sp.csr_matrix([[cat_enc, pri_enc]])
        combined = hstack([text_tfidf, extra])

        raw_dur = duration_predictor.predict(combined)[0]
        dur = max(30, int(round(raw_dur)))

        suggested_description = _description_templates.project_description(cat, text, pri, dur)

        return {
            'category': cat,
            'priority': pri,
            'duration_days': dur,
            'suggested_description': suggested_description
        }
    except Exception:
        return _fallback('project')

def predict_task(text: str) -> dict:
    try:
        load_models()
        _load_description_templates()

        if not _models_loaded:
            return _fallback('task')

        text_lower = _sanitize(text)

        cat = task_classifier.predict([text_lower])[0]
        pri = priority_classifier.predict([text_lower])[0]

        text_tfidf = duration_tfidf.transform([text_lower])
        cat_enc = le_cat.transform([cat])[0]
        pri_enc = le_pri.transform([pri])[0]

        extra = sp.csr_matrix([[cat_enc, pri_enc]])
        combined = hstack([text_tfidf, extra])

        raw_dur = duration_predictor.predict(combined)[0]
        dur = max(1, int(round(raw_dur)))

        suggested_description = _description_templates.task_description(cat, text, pri, dur)

        return {
            'category': cat,
            'priority': pri,
            'duration_days': dur,
            'suggested_description': suggested_description
        }
    except Exception:
        return _fallback('task')
