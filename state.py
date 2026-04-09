import threading

# Secondary guard — set while pyttsx3 is speaking
speaking_lock = threading.Event()

# Tracks whether the PyAudio mic stream is currently open and active
mic_active = threading.Event()
