import os
import warnings
import logging
from typing import Dict, List, Optional, Any, Tuple
import time

# Suppress Hugging Face warnings for clean output
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
warnings.filterwarnings('ignore')

class AIHuggingFace:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.models = {}
        self.pipelines = {}
        
        # Initialize available models
        self._init_models()
    
    def _init_models(self):
        """Initialize available HuggingFace models"""
        self.models = {
            'summarization': 'sshleifer/distilbart-cnn-12-6',
            'text-classification': 'facebook/bart-large-mnli',
            'translation': 'Helsinki-NLP/opus-mt-en-es',
            'sentiment-analysis': 'cardiffnlp/twitter-roberta-base-sentiment-latest',
            'question-answering': 'deepset/roberta-base-squad2',
            'text-generation': 'gpt2',
            'ner': 'dbmdz/bert-large-cased-finetuned-conll03-english',
            'zero-shot-classification': 'facebook/bart-large-mnli'
        }
    
    def _get_pipeline(self, task: str, model_name: Optional[str] = None):
        """Get or create a pipeline for a specific task"""
        try:
            from transformers import pipeline
            
            if task not in self.pipelines:
                model = model_name or self.models.get(task)
                if not model:
                    raise ValueError(f"No model available for task: {task}")
                
                self.pipelines[task] = pipeline(task, model=model)
            
            return self.pipelines[task]
        except Exception as e:
            self.logger.error(f"Error creating pipeline for {task}: {e}")
            return None
    
    def summarize_text(self, text: str, max_length: int = 60, min_length: int = 20) -> Dict[str, Any]:
        """Summarize text using HuggingFace models"""
        try:
            pipeline = self._get_pipeline('summarization')
            if not pipeline:
                return {'success': False, 'error': 'Summarization pipeline not available'}
            
            if len(text) < 50:
                return {'success': False, 'error': 'Text too short for summarization'}
            
            summary = pipeline(text, max_length=max_length, min_length=min_length, do_sample=False)
            return {
                'success': True,
                'summary': summary[0]['summary_text'],
                'original_length': len(text),
                'summary_length': len(summary[0]['summary_text'])
            }
        except Exception as e:
            return {'success': False, 'error': f'Summarization failed: {e}'}
    
    def classify_text(self, text: str, labels: List[str]) -> Dict[str, Any]:
        """Classify text into predefined categories"""
        try:
            pipeline = self._get_pipeline('zero-shot-classification')
            if not pipeline:
                return {'success': False, 'error': 'Classification pipeline not available'}
            
            result = pipeline(text, candidate_labels=labels)
            
            return {
                'success': True,
                'predicted_label': result['labels'][0],
                'confidence': result['scores'][0],
                'all_scores': dict(zip(result['labels'], result['scores']))
            }
        except Exception as e:
            return {'success': False, 'error': f'Classification failed: {e}'}
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        try:
            pipeline = self._get_pipeline('sentiment-analysis')
            if not pipeline:
                return {'success': False, 'error': 'Sentiment analysis pipeline not available'}
            
            result = pipeline(text)
            
            # Map sentiment labels to more readable format
            sentiment_map = {
                'LABEL_0': 'negative',
                'LABEL_1': 'neutral', 
                'LABEL_2': 'positive'
            }
            
            predicted_sentiment = sentiment_map.get(result[0]['label'], result[0]['label'])
            
            return {
                'success': True,
                'sentiment': predicted_sentiment,
                'confidence': result[0]['score'],
                'text': text
            }
        except Exception as e:
            return {'success': False, 'error': f'Sentiment analysis failed: {e}'}
    
    def answer_question(self, question: str, context: str) -> Dict[str, Any]:
        """Answer questions based on context using question-answering model"""
        try:
            pipeline = self._get_pipeline('question-answering')
            if not pipeline:
                return {'success': False, 'error': 'Question-answering pipeline not available'}
            
            result = pipeline(question=question, context=context)
            
            return {
                'success': True,
                'answer': result['answer'],
                'confidence': result['score'],
                'start': result['start'],
                'end': result['end']
            }
        except Exception as e:
            return {'success': False, 'error': f'Question answering failed: {e}'}
    
    def generate_text(self, prompt: str, max_length: int = 100) -> Dict[str, Any]:
        """Generate text based on a prompt"""
        try:
            pipeline = self._get_pipeline('text-generation')
            if not pipeline:
                return {'success': False, 'error': 'Text generation pipeline not available'}
            
            result = pipeline(prompt, max_length=max_length, do_sample=True, temperature=0.7)
            
            return {
                'success': True,
                'generated_text': result[0]['generated_text'],
                'prompt': prompt
            }
        except Exception as e:
            return {'success': False, 'error': f'Text generation failed: {e}'}
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract named entities from text"""
        try:
            pipeline = self._get_pipeline('ner')
            if not pipeline:
                return {'success': False, 'error': 'NER pipeline not available'}
            
            result = pipeline(text)
            
            # Group entities by type
            entities = {}
            for entity in result:
                entity_type = entity['entity']
                if entity_type not in entities:
                    entities[entity_type] = []
                entities[entity_type].append({
                    'text': entity['word'],
                    'confidence': entity['score']
                })
            
            return {
                'success': True,
                'entities': entities,
                'total_entities': len(result)
            }
        except Exception as e:
            return {'success': False, 'error': f'Entity extraction failed: {e}'}
    
    def translate_text(self, text: str, target_language: str = 'es') -> Dict[str, Any]:
        """Translate text to target language"""
        try:
            # Map language codes to model names
            language_models = {
                'es': 'Helsinki-NLP/opus-mt-en-es',
                'fr': 'Helsinki-NLP/opus-mt-en-fr',
                'de': 'Helsinki-NLP/opus-mt-en-de',
                'it': 'Helsinki-NLP/opus-mt-en-it',
                'pt': 'Helsinki-NLP/opus-mt-en-pt',
                'ru': 'Helsinki-NLP/opus-mt-en-ru',
                'ja': 'Helsinki-NLP/opus-mt-en-jap',
                'zh': 'Helsinki-NLP/opus-mt-en-zh'
            }
            
            model_name = language_models.get(target_language)
            if not model_name:
                return {'success': False, 'error': f'Translation to {target_language} not supported'}
            
            pipeline = self._get_pipeline('translation', model_name)
            if not pipeline:
                return {'success': False, 'error': 'Translation pipeline not available'}
            
            result = pipeline(text)
            
            return {
                'success': True,
                'translated_text': result[0]['translation_text'],
                'original_text': text,
                'target_language': target_language
            }
        except Exception as e:
            return {'success': False, 'error': f'Translation failed: {e}'}
    
    def chat(self, message: str, context: Optional[str] = None) -> str:
        """Simple chat interface using text generation"""
        try:
            # Create a context-aware prompt
            if context:
                prompt = f"Context: {context}\nUser: {message}\nAssistant:"
            else:
                prompt = f"User: {message}\nAssistant:"
            
            result = self.generate_text(prompt, max_length=150)
            
            if result['success']:
                # Extract just the assistant's response
                generated = result['generated_text']
                if 'Assistant:' in generated:
                    response = generated.split('Assistant:')[-1].strip()
                else:
                    response = generated.split(prompt)[-1].strip()
                
                return response
            else:
                return f"Sorry, I couldn't process that: {result['error']}"
        except Exception as e:
            return f"Chat error: {e}"
    
    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for HuggingFace AI"""
        cmd_lower = cmd.lower().strip()
        
        if 'summarize' in cmd_lower:
            # Extract text to summarize
            text = cmd_lower.replace('summarize', '').replace('summarise', '').strip()
            if text:
                result = self.summarize_text(text)
                if result['success']:
                    return f"Summary: {result['summary']}"
                else:
                    return f"Summarization failed: {result['error']}"
            else:
                return "Please provide text to summarize"
        
        elif 'sentiment' in cmd_lower or 'emotion' in cmd_lower:
            # Extract text for sentiment analysis
            text = cmd_lower.replace('sentiment', '').replace('emotion', '').replace('analyze', '').replace('analysis', '').strip()
            if text:
                result = self.analyze_sentiment(text)
                if result['success']:
                    return f"Sentiment: {result['sentiment']} (confidence: {result['confidence']:.2f})"
                else:
                    return f"Sentiment analysis failed: {result['error']}"
            else:
                return "Please provide text for sentiment analysis"
        
        elif 'translate' in cmd_lower:
            # Extract text and language for translation
            parts = cmd_lower.replace('translate', '').strip().split(' to ')
            if len(parts) >= 2:
                text = parts[0].strip()
                language = parts[1].strip()
                result = self.translate_text(text, language)
                if result['success']:
                    return f"Translation: {result['translated_text']}"
                else:
                    return f"Translation failed: {result['error']}"
            else:
                return "Please provide text and target language (e.g., 'translate hello to spanish')"
        
        elif 'entities' in cmd_lower or 'extract' in cmd_lower:
            # Extract text for entity extraction
            text = cmd_lower.replace('entities', '').replace('extract', '').strip()
            if text:
                result = self.extract_entities(text)
                if result['success']:
                    entities_str = []
                    for entity_type, entities in result['entities'].items():
                        entity_names = [e['text'] for e in entities]
                        entities_str.append(f"{entity_type}: {', '.join(entity_names)}")
                    return f"Entities found: {'; '.join(entities_str)}"
                else:
                    return f"Entity extraction failed: {result['error']}"
            else:
                return "Please provide text for entity extraction"
        
        elif 'classify' in cmd_lower:
            # Extract text and labels for classification
            parts = cmd_lower.replace('classify', '').strip().split(' as ')
            if len(parts) >= 2:
                text = parts[0].strip()
                labels = [label.strip() for label in parts[1].split(' or ')]
                result = self.classify_text(text, labels)
                if result['success']:
                    return f"Classification: {result['predicted_label']} (confidence: {result['confidence']:.2f})"
                else:
                    return f"Classification failed: {result['error']}"
            else:
                return "Please provide text and categories (e.g., 'classify this as positive or negative')"
        
        else:
            return "Available commands: summarize, sentiment, translate, entities, classify, chat"
    
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return list(self.models.keys())
    
    def get_model_info(self, task: str) -> Dict[str, Any]:
        """Get information about a specific model"""
        if task in self.models:
            return {
                'task': task,
                'model': self.models[task],
                'available': True
            }
        else:
            return {
                'task': task,
                'available': False
            } 