import speech_recognition as sr

class TranscriptionAssistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def transcribe(self):
        with sr.Microphone() as source:
            print('Transcribing...')
            audio = self.recognizer.listen(source)
        try:
            return self.recognizer.recognize_google(audio)  # type: ignore
        except Exception as e:
            return f'Transcription error: {e}' 