print('Loading stt.py...')
from src.logging import logging
from faster_whisper import WhisperModel
import speech_recognition as sr
import src.utils as utils
import requests
import json
import openai
logging.info('Imported required libraries in stt.py')

class Transcriber:
    def __init__(self, conversation_manager):
        self.conversation_manager = conversation_manager
        self.game_interface = self.conversation_manager.game_interface
        self.config = self.conversation_manager.config
        self.language = self.config.stt_language
        self.available_languages = ["af","am","ar","as","az","ba","be","bg","bn","bo","br","bs","ca","cs","cy","da","de","el","en","es","et","eu","fa","fi","fo","fr","gl","gu","ha","haw","he","hi","hr","ht","hu","hy","id","is","it","ja","jw","ka","kk","km","kn","ko","la","lb","ln","lo","lt","lv","mg","mi","mk","ml","mn","mr","ms","mt","my","ne","nl","nn","no","oc","pa","pl","ps","pt","ro","ru","sa","sd","si","sk","sl","sn","so","sq","sr","su","sv","sw","ta","te","tg","th","tk","tl","tr","tt","uk","ur","uz","vi","yi","yo","zh","yue"]
        if self.language == 'auto' or self.language == 'default' or self.language not in self.available_languages:
            self.language = "en"
        self.task = "transcribe"
        if self.config.stt_translate:
            # translate to English
            self.task = "translate"

        # TODO: Whenever a different stt model type is available, need to convert this class to work like the llm and tokenizer classes.
        self.model = self.config.whisper_model
        self.process_device = self.config.whisper_process_device
        self.audio_threshold = self.config.audio_threshold
        self.listen_timeout = self.config.listen_timeout
        self.whisper_type = self.config.whisper_type
        self.whisper_url = self.config.whisper_url

        self.debug_mode = self.config.debug_mode
        self.debug_use_mic = self.config.debug_use_mic
        self.default_player_response = self.config.default_player_response
        self.debug_exit_on_first_exchange = self.config.debug_exit_on_first_exchange
        self.end_conversation_keywords = self.config.end_conversation_keywords

        self.call_count = 0

        self.initialized = False
        if self.game_interface.check_mic_status(): # if mic is enabled, initialize recognizer and microphone
            self.initialize()

    def initialize(self):
        self.initialized = True
        logging.info('Initializing whisper transcriber...')
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = self.config.pause_threshold
        self.microphone = sr.Microphone()

        if self.audio_threshold == 'auto':
            logging.info(f"Audio threshold set to 'auto'. Adjusting microphone for ambient noise...")
            logging.info("If the mic is not picking up your voice, try setting this audio_threshold value manually in PantellaSoftware/config.json.\n")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=5)
        else:
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.energy_threshold = int(self.audio_threshold)
            logging.info(f"Audio threshold set to {self.audio_threshold}. If the mic is not picking up your voice, try lowering this value in PantellaSoftware/config.json. If the mic is picking up too much background noise, try increasing this value.\n")

        # if using faster_whisper, load model selected by player, otherwise skip this step
        if self.whisper_type == 'faster_whisper':
            if self.process_device == 'cuda':
                self.transcribe_model = WhisperModel(
                    self.model,
                    device=self.process_device,
                    compute_type=self.config.whisper_compute_type,
                    cpu_threads=self.config.whisper_cpu_threads
                )
            else:
                self.transcribe_model = WhisperModel(
                    self.model,
                    device=self.process_device,
                    compute_type=self.config.whisper_compute_type,
                    cpu_threads=self.config.whisper_cpu_threads
                )

    def unload(self):
        self.initialized = False
        del self.recognizer
        del self.microphone
        if self.whisper_type == 'faster_whisper':
            del self.transcribe_model


    def get_player_response(self, prompt):
        """Get player response from mic or text input depending on config and MCM settings"""
        if self.debug_mode and not self.debug_use_mic: # use default response
            transcribed_text = self.default_player_response
        else: # use mic or text input
            if self.conversation_manager.game_interface.check_mic_status(): # listen for response
                if not self.initialized:
                    logging.info('Microphone requested but not initialized. Initializing...')
                    self.initialize()
                logging.info('Listening for player response...')
                transcribed_text = self.recognize_input(prompt)
                logging.info(f'Player said: {transcribed_text}')
            else: # use text input
                if self.initialized:
                    logging.info('Microphone not requested but was initialized. Unloading...')
                    self.unload()
                if (self.debug_mode) & (self.debug_use_mic): # text input through console
                    transcribed_text = input('\nWrite player\'s response: ')
                    logging.info(f'Player wrote: {transcribed_text}')
                else: # await text input from the game
                    logging.info('Awaiting text input from the game...')
                    self.game_interface.write_game_info('_pantella_text_input', '') # clear text input before they write
                    self.game_interface.write_game_info('_pantella_text_input_enabled', 'True') # enable text input in the game
                    transcribed_text = self.game_interface.load_data_when_available('_pantella_text_input', '') # wait for player to write and read text input
                    self.game_interface.write_game_info('_pantella_text_input', '') # clear text input after reading
                    self.game_interface.write_game_info('_pantella_text_input_enabled', 'False') # disable text input in the game
                    logging.info(f'Player wrote: {transcribed_text}')
        
        return transcribed_text


    def recognize_input(self, prompt):
        """
        Recognize input from mic and return transcript if activation tag (assistant name) exist
        """
        while True:
            self.game_interface.write_game_info('_pantella_status', 'Listening...')
            logging.info('Listening...')
            transcript = self._recognize_speech_from_mic(prompt)
            transcript_cleaned = utils.clean_text(transcript)

            conversation_ended = self.game_interface.load_data_when_available('_pantella_end_conversation', '')
            if conversation_ended.lower() == 'true':
                return 'goodbye'

            # common phrases hallucinated by Whisper
            if transcript_cleaned in ['', 'thank you', 'thank you for watching', 'thanks for watching', 'the transcript is from the', 'the', 'thank you very much']:
                continue

            self.game_interface.write_game_info('_pantella_status', 'Thinking...')
            return transcript
    

    def _recognize_speech_from_mic(self, prompt):
        """
        Capture the words from the recorded audio (audio stream --> free text).
        Transcribe speech from recorded from `microphone`.
        """
        @utils.time_it
        def whisper_transcribe(audio, prompt):
            # if using faster_whisper (default) return based on faster_whisper's code, if not assume player wants to use server mode and send query to whisper_url set by player.
            if self.whisper_type == 'faster_whisper':
                segments, info = self.transcribe_model.transcribe(audio,
                    task=self.task,
                    language=self.language,
                    beam_size=self.config.beam_size,
                    vad_filter=self.config.vad_filter,
                    initial_prompt=prompt,
                )
                result_text = ' '.join(segment.text for segment in segments)

                return result_text
            # this code queries the whispercpp server set by the user to obtain the response, this format also allows use of official openai whisper API
            else:
                url = self.whisper_url
                if 'openai' in url:
                    headers = {"Authorization": f"Bearer {openai.api_key}",}
                else:
                    headers = {"Authorization": "Bearer apikey",}
                data = {'model': self.model}
                files = {'file': open(audio, 'rb')}
                response = requests.post(url, headers=headers, files=files, data=data)
                response_data = json.loads(response.text)
                if 'text' in response_data:
                    return response_data['text'].strip()

        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=self.listen_timeout)
            except sr.WaitTimeoutError:
                return ''

        audio_file = 'player_recording.wav'
        with open(audio_file, 'wb') as file:
            file.write(audio.get_wav_data(convert_rate=16000))
        
        transcript = whisper_transcribe(audio_file, prompt)
        logging.info(transcript)

        return transcript


    @staticmethod
    def activation_name_exists(transcript_cleaned, activation_name):
        """Identifies keyword in the input transcript"""

        keyword_found = False
        if activation_name in transcript_cleaned:
            keyword_found = True
        if activation_name in transcript_cleaned.lower():
            keyword_found = True
        if activation_name.lower() in transcript_cleaned:
            keyword_found = True
        if activation_name.lower() in transcript_cleaned.lower():
            keyword_found = True
        
        return keyword_found


    @staticmethod
    def _remove_activation_word(transcript, activation_name):
        transcript = transcript.replace(activation_name, '')
        return transcript