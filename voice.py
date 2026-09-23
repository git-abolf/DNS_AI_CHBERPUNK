import threading

class Voice:
    def __init__(self):
        self.tts = None
        try:
            import pyttsx3
            self.tts = pyttsx3.init()
            self.tts.setProperty("rate", 175)
        except Exception:
            pass

    def speak(self, text):
        if not self.tts:
            return
        def run():
            try:
                self.tts.say(text)
                self.tts.runAndWait()
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def listen(self):
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.4)
            audio = r.listen(source, timeout=5, phrase_time_limit=8)
        return r.recognize_google(audio, language="fa-IR")
