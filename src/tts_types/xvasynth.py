print("Loading xvasynth.py")
from src.logging import logging, time
import src.utils as utils
import src.tts_types.base_tts as base_tts
import requests
import subprocess
import sys
import os
from pathlib import Path
import soundfile as sf
import json
import re
import numpy as np
import requests
import threading
import traceback
logging.info("Imported required libraries in xVASynth TTS")

tts_slug = "xvasynth"
class Synthesizer(base_tts.base_Synthesizer): 
    def __init__(self, conversation_manager):
        super().__init__(conversation_manager)
        self.tts_slug = tts_slug
        self.xvasynth_path = self.config.xvasynth_path
        self.process_device = self.config.xvasynth_process_device
        self.times_checked_xvasynth = 0
        
        self.check_if_xvasynth_is_running()

        self.pace = self.config.pace
        self.use_sr = self.config.use_sr
        self.use_cleanup = self.config.use_cleanup

        self.last_voice = ''
        self.model_type = ''
        self.base_speaker_emb = ''
        
        # voice models path
        if not self.config.linux_mode:
            if not os.path.exists(f"{self.xvasynth_path}\\resources\\"):
                logging.error(f"xVASynth path invalid: {self.xvasynth_path}")
                logging.error(f"Please ensure that the path to xVASynth is correct in config.json (xvasynth_path)")
                input('\nPress any key to stop Pantella...')
                raise FileNotFoundError(f"xVASynth path invalid: {self.xvasynth_path}")
        else:
            if not os.path.exists(f"{self.xvasynth_path}/resources/"):
                logging.error(f"xVASynth path invalid: {self.xvasynth_path}")
                logging.error(f"Please ensure that the path to xVASynth is correct in config.json (xvasynth_path)")
                input('\nPress any key to stop Pantella...')
                raise FileNotFoundError(f"xVASynth path invalid: {self.xvasynth_path}")
            
        if self.game == "fallout4" or self.game == "fallout4vr": # get the correct voice model for Fallout 4
            self.model_path = f"{self.xvasynth_path}/resources/app/models/fallout4/"
        else:
            self.model_path = f"{self.xvasynth_path}/resources/app/models/skyrim/"

        self.synthesize_url = f'{self.config.xvasynth_base_url}/synthesize'
        self.synthesize_batch_url = f'{self.config.xvasynth_base_url}/synthesize_batch'
        self.loadmodel_url = f'{self.config.xvasynth_base_url}/loadModel'
        self.setvocoder_url = f'{self.config.xvasynth_base_url}/setVocoder'
        self.get_available_voices_url = f'{self.config.xvasynth_base_url}/getAvailableVoices'
        self.set_available_voices_url = f'{self.config.xvasynth_base_url}/setAvailableVoices'
        logging.config(f'xVASynth - Available voices: {self.voices()}')
        
    def _say(self, voiceline, voice_model="Female Sultry", volume=0.5):
        self.change_voice(voice_model)
        voiceline_location = f"{self.output_path}\\voicelines\\{self.last_voice}\\direct.wav"
        if not os.path.exists(voiceline_location):
            os.makedirs(os.path.dirname(voiceline_location), exist_ok=True)
        self._synthesize_line(voiceline, voiceline_location)
        self.play_voiceline(voiceline_location, volume)
        
    def check_if_xvasynth_is_running(self):
        """Check if xVASynth is running and start it if it isn't"""
        self.times_checked_xvasynth += 1

        try:
            if (self.times_checked_xvasynth > 20):
                # break loop
                logging.error('Could not connect to xVASynth multiple times. Ensure that xVASynth is running and restart Pantella.')
                input('\nPress any key to stop Pantella...')
                sys.exit(0)

            # contact local xVASynth server; ~2 second timeout
            logging.info(f'Attempting to connect to xVASynth... ({self.times_checked_xvasynth})')
            response = requests.get(f'{self.config.xvasynth_base_url}/')
            response.raise_for_status()  # If the response contains an HTTP error status code, raise an exception
        except requests.exceptions.RequestException as err:
            if (self.times_checked_xvasynth == 1):
                logging.info('Could not connect to xVASynth. Attempting to run headless server...')
                self.run_xvasynth_server()
            time.sleep(2)
            # do the web request again; LOOP!!!
            return self.check_if_xvasynth_is_running()

    def run_xvasynth_server(self):
        """Run xVASynth server in headless mode - Required for xVASynth to work with Pantella"""
        try:
            # start the process without waiting for a response
            if not self.config.linux_mode:
                subprocess.Popen(f'{self.xvasynth_path}/resources/app/cpython_{self.process_device}/server.exe', cwd=self.xvasynth_path)
            else:
                command = f'CUDA_VISIBLE_DEVICES= python3 {self.xvasynth_path}resources/app/server.py'
                logging.info(f'Running xVASynth server with command: {command}')
                # subprocess.run(command, shell=False, cwd=self.xvasynth_path)
                if self.process_device == "cpu":
                    threading.Thread(target=subprocess.run, args=(command,), kwargs={'shell': True, 'cwd': self.xvasynth_path}).start()
                else:
                    threading.Thread(target=subprocess.run, args=(command,), kwargs={'shell': True, 'cwd': self.xvasynth_path}).start()

        except Exception as e:
            logging.error(f'Could not run xVASynth. Ensure that the path "{self.xvasynth_path}" is correct.')
            logging.error(e)
            tb = traceback.format_exc()
            logging.error(tb)
            input('\nPress any key to stop Pantella...')
            raise e
 
    def synthesize(self, voiceline, character, aggro=0):
        """Synthesize the voiceline for the character specified using xVASynth"""
        if character.voice_model != self.last_voice:
            self.change_voice(character)
        voiceline = ' ' + voiceline + ' ' # xVASynth apparently performas better having spaces at the start and end of the voiceline for some reason

        if voiceline.strip() == '': # If the voiceline is empty, don't synthesize anything
            logging.info('No voiceline to synthesize.')
            return ''

        logging.info(f'Synthesizing voiceline: {voiceline}')
        phrases = self._split_voiceline(voiceline)

        # make voice model folder if it doesn't already exist
        if not os.path.exists(f"{self.output_path}\\voicelines\\{self.last_voice}"):
            os.makedirs(f"{self.output_path}\\voicelines\\{self.last_voice}")
        
        voiceline_files = []
        for phrase in phrases:
            voiceline_file = f"{self.output_path}\\voicelines\\{self.last_voice}\\{utils.clean_text(phrase)[:150]}.wav"
            voiceline_files.append(voiceline_file)

        final_voiceline_file_name = 'voiceline'
        final_voiceline_file =  f"{self.output_path}\\voicelines\\{self.last_voice}\\{final_voiceline_file_name}.wav"

        try:
            if os.path.exists(final_voiceline_file): # Remove old voiceline file
                os.remove(final_voiceline_file) 
            if os.path.exists(final_voiceline_file.replace(".wav", ".lip")): # Remove old lip file
                os.remove(final_voiceline_file.replace(".wav", ".lip"))
        except:
            logging.warning("Failed to remove spoken voicelines") # If it fails, it fails

        # Synthesize voicelines
        if len(phrases) == 1:
            self._synthesize_line(phrases[0], final_voiceline_file, character, aggro)
        else:
            # TODO: include batch synthesis for v3 models (batch not needed very often)
            if self.model_type != 'xVAPitch':
                self._batch_synthesize(phrases, voiceline_files)
            else:
                for i, voiceline_file in enumerate(voiceline_files):
                    self._synthesize_line(phrases[i], voiceline_files[i], character)
            self.merge_audio_files(voiceline_files, final_voiceline_file)

        if not os.path.exists(final_voiceline_file):
            logging.error(f'xVASynth failed to generate voiceline at: {Path(final_voiceline_file)}')
            raise FileNotFoundError()
        
        self.lip_gen(voiceline, final_voiceline_file)
        self.debug(final_voiceline_file)

        return final_voiceline_file
    
    def voices(self): # Send API request to xvasynth to get a list of characters
        """Return a list of available voices"""
        logging.config(f"Getting available voices from {self.get_available_voices_url}...")
        requests.post(self.set_available_voices_url, json={'modelsPaths': json.dumps({self.game: self.model_path})}) # Set the available voices to the ones in the models folder
        r = requests.post(self.get_available_voices_url) # Get the available voices
        if r.status_code == 200:
            logging.config(f"Got available voices from {self.get_available_voices_url}...")
            # logging.info(f"Response code: {r.status_code}")
            # logging.info(f"Response text: {r.text}")
            data = r.json()
        else:
            logging.info(f"Could not get available voices from {self.get_available_voices_url}...")
            # logging.info(f"Response code: {r.status_code}")
            # logging.info(f"Response text: {r.text}")
            data = None
        voices = []
        for character in data[self.game]:
            voices.append(character['voiceName'])
        logging.config(f"Available xVASynth Voices: {voices}")
        logging.config(f"Total xVASynth Voices: {len(voices)}")
        return voices

    @utils.time_it
    def _synthesize_line(self, line, save_path, character=None, aggro=0):
        """Synthesize a line using xVASynth"""
        pluginsContext = {}
        # in combat
        if (aggro == 1):
            pluginsContext["mantella_settings"] = {
                "emAngry": 0.6
            }
        base_lang = character.tts_language_code if character else self.language["tts_language_code"] # TODO: Make sure this works
        data = {
            'pluginsContext': json.dumps(pluginsContext),
            'modelType': self.model_type,
            'sequence': line,
            'pace': self.pace,
            'outfile': save_path,
            'vocoder': 'n/a',
            'base_lang': base_lang,
            'base_emb': self.base_speaker_emb,
            'useSR': self.use_sr,
            'useCleanup': self.use_cleanup,
        }
        logging.out(f'Synthesizing voiceline: {line}')
        logging.config(f'Saving to: {save_path}')
        logging.info(f'Voice model: {self.last_voice}')
        logging.config(f'Base language: {base_lang}')
        # logging.info(f'Base speaker emb: {self.base_speaker_emb}') # Too spammy
        logging.config(f'Pace: {self.pace}')
        logging.config(f'Use SR: {self.use_sr}')
        logging.config(f'Use Cleanup: {self.use_cleanup}')
        requests.post(self.synthesize_url, json=data)

    @utils.time_it
    def _batch_synthesize(self, grouped_sentences, voiceline_files):
        """Batch synthesize multiple lines using xVASynth"""
        # line = [text, unknown 1, unknown 2, pace, output_path, unknown 5, unknown 6, pitch_amp]
        linesBatch = [[grouped_sentences[i], '', '', self.pace, voiceline_files[i], '', '', 1] for i in range(len(grouped_sentences))]
        
        data = {
            'pluginsContext': '{}',
            'modelType': self.model_type,
            'linesBatch': linesBatch,
            'speaker_i': None,
            'vocoder': [],
            'outputJSON': None,
            'useSR': None,
            'useCleanup': None,
        }
        requests.post(self.synthesize_batch_url, json=data)

    @utils.time_it
    def _group_sentences(self, voiceline_sentences, max_length=150):
        """
        Splits sentences into separate voicelines based on their length (max=max_length)
        Groups sentences if they can be done so without exceeding max_length
        """
        grouped_sentences = []
        temp_group = []
        for sentence in voiceline_sentences:
            if len(sentence) > max_length:
                grouped_sentences.append(sentence)
            elif len(' '.join(temp_group + [sentence])) <= max_length:
                temp_group.append(sentence)
            else:
                grouped_sentences.append(' '.join(temp_group))
                temp_group = [sentence]
        if temp_group:
            grouped_sentences.append(' '.join(temp_group))

        return grouped_sentences
    

    @utils.time_it
    def _split_voiceline(self, voiceline, max_length=150):
        """Split voiceline into phrases by commas, 'and', and 'or'"""

        # Split by commas and "and" or "or"
        chunks = re.split(r'(, | and | or )', voiceline)
        # Join the delimiters back to their respective chunks
        chunks = [chunks[i] + (chunks[i+1] if i+1 < len(chunks) else '') for i in range(0, len(chunks), 2)]
        # Filter out empty chunks
        chunks = [chunk for chunk in chunks if chunk.strip()]

        result = []
        for chunk in chunks:
            if len(chunk) <= max_length:
                if result and result[-1].endswith(' and'):
                    result[-1] = result[-1][:-4]
                    chunk = 'and ' + chunk.strip()
                elif result and result[-1].endswith(' or'):
                    result[-1] = result[-1][:-3]
                    chunk = 'or ' + chunk.strip()
                result.append(chunk.strip())
            else:
                # Split long chunks based on length
                words = chunk.split()
                current_line = words[0]
                for word in words[1:]:
                    if len(current_line + ' ' + word) <= max_length:
                        current_line += ' ' + word
                    else:
                        if current_line.endswith(' and'):
                            current_line = current_line[:-4]
                            word = 'and ' + word
                        if current_line.endswith(' or'):
                            current_line = current_line[:-3]
                            word = 'or ' + word
                        result.append(current_line.strip())
                        current_line = word
                result.append(current_line.strip())

        result = self._group_sentences(result, max_length)
        logging.info(f'Split sentence into:',result)

        return result

    def merge_audio_files(self, audio_files, voiceline_file_name):
        """Merge multiple audio files into one file"""
        logging.info(f'Merging audio files: {audio_files}')
        logging.info(f'Output file: {voiceline_file_name}')
        merged_audio = np.array([])

        for audio_file in audio_files:
            try:
                audio, samplerate = sf.read(audio_file)
                merged_audio = np.concatenate((merged_audio, audio))
            except:
                logging.info(f'Could not find voiceline file: {audio_file}')

        sf.write(voiceline_file_name, merged_audio, samplerate)
  
    @utils.time_it
    def change_voice(self, character):
        """Change the voice model to the specified character's voice model"""
        if type(character) == str:
            voice = character
        else:
            voice = self.get_valid_voice_model(character) # character.voice_model

        if voice is None:
            logging.error(f'Voice model {character.voice_model} not available! Please add it to xVASynth voices list.')
        if self.crashable and voice is None:
            input("Press enter to continue...")
            raise base_tts.VoiceModelNotFound(f'Voice model {character.voice_model} not available! Please add it to xVASynth voices list.')

        logging.info(f'Loading voice model {voice}...')
        
        # TODO: Enhance to check every game for any voice model, just prefer the one for the current game if available
        if self.game == "fallout4" or self.game == "fallout4vr": # get the correct voice model for Fallout 4
            logging.config("Checking for Fallout 4 voice model...")
            XVASynthAcronym="f4_"
            XVASynthModNexusLink="https://www.nexusmods.com/fallout4/mods/49340?tab=files"
        else: # get the correct voice model for Skyrim
            logging.config("Checking for Skyrim voice model...")
            XVASynthAcronym="sk_"
            XVASynthModNexusLink = "https://www.nexusmods.com/skyrimspecialedition/mods/44184?tab=files"
        voice_path = f"{self.model_path}{XVASynthAcronym}{voice.lower().replace(' ', '')}"
        
        if not os.path.exists(voice_path+'.json'):
            logging.error(f"Voice model does not exist in location '{voice_path}'. Please ensure that the correct path has been set in config.json (xvasynth_folder) and that the model has been downloaded from {XVASynthModNexusLink} (Ctrl+F for '{XVASynthAcronym}{voice.lower().replace(' ', '')}').")
            raise base_tts.VoiceModelNotFound()

        with open(voice_path+'.json', 'r', encoding='utf-8') as f:
            voice_model_json = json.load(f)

        try:
            base_speaker_emb = voice_model_json['games'][0]['base_speaker_emb']
            base_speaker_emb = str(base_speaker_emb).replace('[','').replace(']','')
        except:
            base_speaker_emb = None

        self.base_speaker_emb = base_speaker_emb
        self.model_type = voice_model_json.get('modelType')
        
        model_change = {
            'outputs': None,
            'version': '3.0',
            'model': voice_path, 
            'modelType': self.model_type,
            'base_lang': character.tts_language_code if type(character) != str else 'en',
            'pluginsContext': '{}',
        }
        requests.post(self.loadmodel_url, json=model_change)

        self.last_voice = voice
        logging.info('Voice model loaded.')
