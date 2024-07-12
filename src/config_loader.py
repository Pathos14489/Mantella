print("Importing config_loader.py")
from src.logging import logging
import json
import os
import flask
logging.info("Imported required libraries in config_loader.py")

game_configs = {}
# Get all game configs from src/game_configs/ and add them to game_configs
for file in os.listdir(os.path.join(os.path.dirname(__file__), "../game_configs/")):
    if file.endswith(".json") and not file.startswith("__"):
        logging.info(f"Importing game config {file}")
        game_id = file[:-5]
        logging.info(f"Game id: {game_id}")
        game_configs[game_id] = json.load(open(os.path.join(os.path.dirname(__file__), "../game_configs", file)))
        logging.info(f"Imported game config {game_id}")
logging.info("Imported all game configs, ready to use them!")

class ConfigLoader:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.prompt_styles = {}
        self._raw_prompt_styles = {}
        self.behavior_styles = {}
        self._raw_behavior_styles = {}
        self.get_behavior_styles()
        self.load()
        self.game_configs = game_configs
        self.current_game_config = game_configs[self.game_id]
        logging.info(f"ConfigLoader initialized with config path {config_path}")
        logging.info(f"Current game config: '{self.current_game_config}' from game id '{self.game_id}'")
        self.conversation_manager_type = self.current_game_config["conversation_manager_type"]
        self.interface_type = self.current_game_config["interface_type"]
        self.behavior_manager = self.current_game_config["behavior_manager"]
        logging.log_file = self.logging_file_path # Set the logging file path
        self.get_prompt_styles()
        self.ready = True

    @property
    def game_path(self):
        return self.current_game_config["game_path"]
    
    @property
    def mod_path(self):
        return self.current_game_config["mod_path"]

    def save(self):
        """Save the config to the config file"""
        try:
            export_obj = self.export()
        except Exception as e:
            logging.error(f"Could not save config file to {self.config_path}. Error: {e}")
            raise e
        try:
            with open(self.config_path, 'w') as f:
                json.dump(export_obj, f, indent=4)
            logging.info(f"Config file saved to {self.config_path}")
        except Exception as e:
            logging.error(f"Could not save config file to {self.config_path}. Error: {e}")
            raise e

    def load(self):
        """Load the config from the config file and set the settings to the loader. If the config file does not exist, create it with the default settings. If a setting is missing from the config file, set it to the default setting."""
        print(f"Loading config from {self.config_path}")
        save = False
        default = self.default()
        if os.path.exists(self.config_path):
            # If the config file does not exist, create it
            try:
                config = json.load(open(self.config_path))
            except:
                new_config = input(f"Error: Could not load config file from {self.config_path}. Do you want to create a new config file with default settings? (y/n): ")
                if new_config.lower() == "y":
                    config = self.default()
                    save = True
                    print(f"Saving default config file to {self.config_path}")
                else:
                    logging.error(f"Could not load config file from {self.config_path}.")
                    input("Press enter to continue...")
                    raise ValueError(f"Could not load config file from {self.config_path}. Exiting...")

        else:
            logging.error(f"\"{self.config_path}\" does not exist! Creating default config file...")
            config = self.default()
            save = True
            print(f"Saving default config file to {self.config_path}")
        
        for key in default: # Set the settings in the config file to the default settings if they are missing
            if key not in config:
                config[key] = default[key]
                save = True
                print(f"Saving new key '{key}' to config file")
            for sub_key in default[key]:
                if sub_key not in config[key]:
                    config[key][sub_key] = default[key][sub_key]
                    save = True
                    print(f"Saving new subkey '{key}':'{sub_key}' to config file")
                    
        for key in default: # Set the config settings to the loader
            for sub_key in default[key]:
                # print(f"Setting {sub_key} to {config[key][sub_key]}")
                if "_path" in sub_key or "_file" in sub_key:
                    setattr(self, sub_key, config[key][sub_key].replace("\\", "/").replace("/","\\"))
                else:
                    setattr(self, sub_key, config[key][sub_key])

        if self.game_id not in game_configs:
            logging.error(f"Game id {self.game_id} not found in game_configs directory. Please add a game config file for {self.game_id} or change the game_id in config.json to a valid game id.")
            logging.info(f"Valid game ids: {list(game_configs.keys())}")
            input("Press enter to continue...")
            raise ValueError(f"Game id {self.game_id} not found in game_configs directory. Please add a game config file for {self.game_id} or change the game_id in config.json to a valid game id.")

        if save:
            self.save()
            
        if self.linux_mode:
            logging.info("Linux mode enabled - Fixing paths for linux...")
            # Fix paths for linux
            for key in default:
                for sub_key in default[key]:
                    if "_path" in sub_key or "_file" in sub_key or "_dirlol" in sub_key:
                        setattr(self, sub_key, config[key][sub_key].replace("\\", "/"))
            logging.info("Paths fixed for linux")
        
        self.set_behavior_style(self.behavior_style)

        logging.info(f"Unique settings:", self.unique())
        logging.info(f"Config loaded from {self.config_path}")

    def get_prompt_styles(self):
        """Get the prompt styles from the prompt_styles directory"""
        logging.info("Getting prompt styles")
        prompt_styles_dir = os.path.join(os.path.dirname(__file__), "../prompt_styles/")
        for file in os.listdir(prompt_styles_dir):
            if file.endswith('.json'):
                with open(f'{prompt_styles_dir}/{file}') as f:
                    slug = file.split('.')[0]
                    self._raw_prompt_styles[slug] = json.load(f)
                    self.prompt_styles[slug] = self._raw_prompt_styles[slug]
        style_names = [f"{slug} ({self._raw_prompt_styles[slug]['name']})" for slug in self.prompt_styles]
        logging.info(f"Prompt styles loaded: "+str(style_names))

    def get_behavior_styles(self):
        """Get the behavior styles from the behavior_styles directory"""
        logging.info("Getting behavior styles")
        behavior_styles_dir = os.path.join(os.path.dirname(__file__), "../behavior_styles/")
        for file in os.listdir(behavior_styles_dir):
            if file.endswith('.json'):
                with open(f'{behavior_styles_dir}/{file}') as f:
                    slug = file.split('.')[0]
                    self._raw_behavior_styles[slug] = json.load(f)
                    self.behavior_styles[slug] = self._raw_behavior_styles[slug]["behavior_style"]
        style_names = [f"{slug} ({self._raw_behavior_styles[slug]['name']})" for slug in self.behavior_styles]
        logging.info(f"Behavior styles loaded: "+str(style_names))

    @property
    def prompts(self):
        return self.language["prompts"]
    
    @property
    def stop(self):
        return self._prompt_style["style"]["stop"]
    @property
    def BOS_token(self):
        return self._prompt_style["style"]["BOS_token"]
    @property
    def EOS_token(self):
        return self._prompt_style["style"]["EOS_token"]
    @property
    def message_signifier(self):
        return self._prompt_style["style"]["message_signifier"]
    @property
    def role_seperator(self):
        return self._prompt_style["style"]["role_seperator"]
    @property
    def message_separator(self):
        return self._prompt_style["style"]["message_separator"]
    @property
    def message_format(self):
        return self._prompt_style["style"]["message_format"]
    @property
    def system_name(self):
        return self._prompt_style["style"]["system_name"]
    @property
    def user_name(self):
        return self._prompt_style["style"]["user_name"]
    @property
    def assistant_name(self):
        return self._prompt_style["style"]["assistant_name"]
    @property
    def language(self):
        return self._prompt_style["language"]
    @property
    def racial_language(self):
        return self._prompt_style["racial_language"]
    
    def set_prompt_style(self, llm):
        """Set the prompt style - if llm has a recommended prompt style and config.prompt_style is not set to a specific style, set it to the recommended style"""
        if self.prompt_style is not None:
            if llm.prompt_style in self.prompt_styles and self.prompt_style == "default":
                self._prompt_style = self.prompt_styles[llm.prompt_style]
            elif self.prompt_style in self.prompt_styles:
                self._prompt_style = self.prompt_styles[self.prompt_style]
            else:
                logging.error(f"Prompt style {self.prompt_style} not found in prompt_styles directory. Using default prompt style.")
                self._prompt_style = self.prompt_styles["normal_en"]
        else:
            logging.error(f"Prompt style not set in config file. Using default prompt style.")
            self._prompt_style = self.prompt_styles["normal_en"]
        # self.get_tokenizer_settings_from_prompt_style()
        logging.info("Getting tokenizer settings from prompt style")
        logging.info(self._prompt_style)
        logging.info("Prompt formatting settings loaded")
    
    def set_behavior_style(self, behavior_style):
        """Set the behavior style - if behavior_style is not set to a specific style, set it to the default style"""
        if behavior_style is not None:
            if behavior_style in self.behavior_styles:
                self._behavior_style = self.behavior_styles[behavior_style]
            else:
                logging.error(f"Behavior style {behavior_style} not found in behavior_styles directory. Using default behavior style.")
                self._behavior_style = self.behavior_styles["normal"]
        else:
            logging.error(f"Behavior style not set in config file. Using default behavior style.")
            self._behavior_style = self.behavior_styles["normal"]
        return self._behavior_style

    def default(self):
        return {
            "Game": {
                "game_id": "skyrim", # skyrim, skyrimvr, fallout4 or fallout4vr
                "conversation_manager_type": "auto",
                "interface_type": "auto",
                "behavior_manager": "auto",
                "memory_manager": "auto"
            },
            "summarizing_memory":{
                "summary_limit_pct": 0.8,
                "summarizing_memory_direction": "topdown", # topdown or bottomup
                "summarizing_memory_depth": 1,
            },
            "chromadb_memory":{
                "memory_update_interval": 1,
                "logical_memories": 5,
                "emotional_memories": 5,
                "torchmoji_max_length": 30,
                "empathy": 0.5,
                "chromadb_memory_messages_before": 4,
                "chromadb_memory_messages_after": 2,
                "emotional_decay_min": 0.005,
                "emotional_decay_max": 0.01,
                "emotion_composition": {
                    "amused": [
                        "joy",
                        "speak_no_evil",
                        "wink",
                    ],
                    "happy": [
                        "ok_hand",
                        "grin",
                        "v",
                        "sunglasses",
                        "yum",
                        "smile",
                        "stuck_out_tongue_winking_eye",
                        "relieved",
                        "thumbsup",
                        "sparkles",
                        "muscle",
                        "raised_hands",
                        "cry",
                        "musical_note",
                        "notes",
                        "clap"
                    ],
                    "sad": [
                        "unamused",
                        "tired_face",
                        "sob",
                        "cry",
                        "persevere",
                        "broken_heart",
                        "sleepy",
                        "pensive"
                    ],
                    "trusting": [
                        "relaxed",
                        "pray",
                    ],
                    "afraid": [
                        "weary",
                        "sweat_smile",
                        "skull",
                    ],
                    "angry": [
                        "rage",
                        "triumph",
                        "angry",
                        "facepunch",
                        "information_desk_person",
                        "disappointed",
                    ],
                    "regretful": [
                        "disappointed",
                        "speak_no_evil",
                        "pensive",
                    ],
                    "infatuated": [
                        "heart_eyes",
                        "blush",
                        "heart",
                        "flushed",
                        "two_hearts",
                        "kissing_heart",
                        "heartbeat",
                        "yellow_heart",
                        "purple_heart",
                        "sparkling_heart",
                        "blue_heart"
                    ],
                    "flirtaious": [
                        "wink",
                        "smirk",
                        "musical_note",
                        "notes",
                    ],
                    "confused": [
                        "confused",
                        "sweat",
                        "confounded",
                        "grimacing",
                    ],
                    "curious": [
                        "eyes",
                        "see_no_evil",
                    ],
                    "cheerful": [
                        "smiling_imp",
                        "gun",
                        "see_no_evil",
                        "musical_note",
                        "notes",
                        "wink",
                    ]
                },
                "chromadb_memory_depth": 1,
                "chromadb_memory_direction": "topdown", # topdown or bottomup
                "chromadb_query_size": 5,
            },
            "Microphone": {
                "whisper_model": "base",
                "stt_language": "default",
                "stt_translate": False,
                "whisper_process_device": "cpu",
                "whisper_type": "faster_whisper",
                "whisper_url": "http://127.0.0.1:8080/inference",
                "audio_threshold": "auto",
                "pause_threshold": 0.5,
                "listen_timeout": 30,
                "whisper_cpu_threads": 4,
                "whisper_compute_type": "auto",
                "beam_size": 5,
                "vad_filter": True,
            },
            "LanguageModel": {
                "inference_engine": "default",
                "tokenizer_type": "default",
                "maximum_local_tokens": 4096,
                "max_response_sentences": 999,
                "wait_time_buffer": 1.0,
                "same_output_limit": 30,
                "conversation_limit_pct": 0.9,
                "min_conversation_length": 5,
                "reload_buffer": 20,
                # "reload_wait_time": 1,
            },
            "PromptStyle":{
                "prompt_style": "default",
                "behavior_style": "normal",
                "conversation_start_type": "force_npc_greeting_for_first_meeting_then_llm_choice",
                "strip_smalls": True, # Skip small voicelines
                "small_size": 3, # Character length that defines a small voiceline
                "assure_grammar": True,
                "assist_check": False,
                "break_on_time_announcements": True,
                "as_a_check": False,
                "meet_string_game_events": False,
                "game_update_pruning": True,
                "game_update_prune_count": 5,
                "conversation_start_role": "system", # "system" or "user" is recommended, "assistant" is not recommended because it would teach the assstant that it can respond using your identity, which is not recommended as it will waste generations failing to generate messages from you
                "custom_possible_player_aliases": [], # adds additional names the player goes by to the list of names to check for in the conversation start role
            },
            "InferenceOptions": {
                "temperature": 0.8,
                "top_p": 1,
                "min_p": 0.05,
                "typical_p": 0.9,
                "top_k": 0,
                "repeat_penalty": 1.0,
                "tfs_z": 1.0,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "mirostat_mode": 0,
                "mirostat_eta": 0.1,
                "mirostat_tau": 5,
                "max_tokens": 512,
            },
            "openai_api": {
                "llm": "undi95/toppy-m-7b:free",
                "alternative_openai_api_base": "https://openrouter.ai/api/v1/",
                "secret_key_file_path": ".\\GPT_SECRET_KEY.txt",
                "banned_samplers": [], # Examples: "min_p", "typical_p", "top_p", "top_k", "temperature", "frequency_penalty", "presence_penalty", "repeat_penalty", "tfs_z", "mirostat_mode", "mirostat_eta", "mirostat_tau", "max_tokens"
            },
            "llama_cpp_python": {
                "model_path": ".\\model.gguf",
                "n_gpu_layers": 0,
                "n_threads": 4,
                "n_batch": 512,
                "tensor_split": [], # [0.5,0.5] for 2 gpus split evenly, [0.3,0.7] for 2 gpus split unevenly
                "main_gpu": 0,
                "split_mode": 0, # 0 = single gpu, 1 = split layers and kv across gpus, 2 = split rows across gpus
                "use_mmap": True,
                "use_mlock": False,
                "n_threads_batch": 1,
                "offload_kqv": True,
            },
            "llava_cpp_python": {
                "llava_clip_model_path": ".\\clip_model.gguf",
                "ocr_lang": "en",
                "ocr_use_angle_cls": True,
                "ocr_filter":[
                    "Skyrim Special Edition",
                    "Fallout 4",
                    "E",
                    "Talk",
                    "Steal",
                    "Take",
                    "Use",
                    "Read",
                    "Open",
                    "Close",
                    "Activate",
                    "Search",
                    "Pick",
                    "Unlock",
                    "Lock",
                    "Sleep",
                    "Wait",
                    "Sit",
                ],
                "append_system_image_near_end": True,
                "llava_image_message_depth": -1,
                "llava_image_message": "The image below is {player_perspective_name}'s perspective:\n<image>\n<ocr>",
                "paddle_ocr": True,
                "ocr_resolution": 256,
                "clip_resolution": 672,
            },
            "transformers": {
                "transformers_model_slug": "mistralai/Mistral-7B-Instruct-v0.1",
                "trust_remote_code": False,
                "device_map": "cuda:0", # "cuda", "cuda:0", "cuda:1", "auto"
                "load_in_8bit": False
            },
            "Speech": {
                "tts_engine": ["xvasynth"],
                "end_conversation_wait_time": 1,
                "sentences_per_voiceline": 2,
                "narrator_voice": "MaleKhajiit",
                "narrator_volume": 0.5, # 50% volume
                "narrator_delay": 0.2, # 200ms delay
            },
            "xVASynth": {
                "xvasynth_path": "C:\\Games\\Steam\\steamapps\\common\\xVASynth",
                "xvasynth_process_device": "cpu",
                "pace": 1.0,
                "use_cleanup": False,
                "use_sr": False,
                "xvasynth_base_url": "http://127.0.0.1:8008"
            },
            "xTTS": {
                "xtts_device": "cuda",
                "xtts_voice_samples_dir": ".\\data\\voice_samples",
                "xtts_preload_latents": True,
                "xtts_use_cached_latents": True,
                "xtts_temperature": 0.75,
                "xtts_top_k": 50,
                "xtts_top_p": 0.85,
                "xtts_length_penalty": 1.0,
                "xtts_repetition_penalty": 10.0,
                "xtts_speed": 1.0,
                "xtts_num_beams": 1,
            },
            "xTTS_api": {
                "xtts_api_base_url": "http://127.0.0.1:8020",
                "xtts_api_data": {
                    "temperature": 0.75,
                    "length_penalty": 1.0,
                    "repetition_penalty": 3.0,
                    "top_k": 40,
                    "top_p": 0.80,
                    "speed": 1.25,
                    "enable_text_splitting": True,
                    "stream_chunk_size": 200
                },
                "default_xtts_api_model": "v2.0.2"
            },
            "Debugging": {
                "debug_mode": False,
                "share_debug_ui": False,
                "remove_mei_folders": False,
                "play_audio_from_script": False,
                "debug_character_name": "Hulda",
                "debug_use_mic": False,
                "default_player_response": "Can you tell me something about yourself?",
                "add_voicelines_to_all_voice_folders": False
            },
            "Errors": {
                "continue_on_voice_model_error": False,
                "continue_on_missing_character": False,
                "continue_on_llm_api_error": True,
                "bad_author_retries": 5,
                "retries": 3,
                "system_loop": 3,
            },
            "Config": {
                "linux_mode": False,
                "character_database_file": ".\\characters\\", # can be a csv file path, a directory file path, or a list of csv file paths and directory file paths
                "conversation_data_directory": ".\\data\\conversations",
                "voice_model_ref_ids_file": ".\\skyrim_voice_model_ids.json",
                "logging_file_path": ".\\logging.log",
                "port": 8021
            }
        }
    
    def _unique(self):
        """Return a dictionary of settings that have been changed from the default settings"""
        default = self.default()
        unique = {}
        for key in default:
            for sub_key in default[key]:
                if getattr(self, sub_key) != default[key][sub_key]:
                    if key not in unique:
                        unique[key] = {}
                    unique[key][sub_key] = getattr(self, sub_key)
        return unique
    
    def unique(self):
        """Return a dictionary of settings that have been changed from the default settings"""
        return json.dumps(self._unique(), indent=4)

    def descriptions(self):
        """Return a dictionary of descriptions for each setting"""
        with open('./settings_descriptions.json') as f:
            return json.load(f)

    def export(self):
        return {
            "Game": {
                "game_id": self.game_id,
                "conversation_manager_type": self.conversation_manager_type,
                "interface_type": self.interface_type,
                "behavior_manager": self.behavior_manager,
                "memory_manager": self.memory_manager
            },
            "summarizing_memory": {
                "summary_limit_pct": self.summary_limit_pct,
                "summarizing_memory_direction": self.summarizing_memory_direction,
                "summarizing_memory_depth": self.summarizing_memory_depth,
            },
            "chromadb_memory": {
                "memory_update_interval": self.memory_update_interval,
                "logical_memories": self.logical_memories,
                "emotional_memories": self.emotional_memories,
                "torchmoji_max_length": self.torchmoji_max_length,
                "empathy": self.empathy,
                "chromadb_memory_messages_before": self.chromadb_memory_messages_before,
                "chromadb_memory_messages_after": self.chromadb_memory_messages_after,
                "emotional_decay_min": self.emotional_decay_min,
                "emotional_decay_max": self.emotional_decay_max,
                "emotion_composition": self.emotion_composition,
                "chromadb_memory_depth": self.chromadb_memory_depth,
                "chromadb_memory_direction": self.chromadb_memory_direction,
                "chromadb_query_size": self.chromadb_query_size,
            },
            "Microphone": {
                "whisper_model": self.whisper_model,
                "stt_language": self.stt_language,
                "stt_translate": self.stt_translate,
                "whisper_process_device": self.whisper_process_device,
                "whisper_type": self.whisper_type,
                "whisper_url": self.whisper_url,
                "audio_threshold": self.audio_threshold,
                "pause_threshold": self.pause_threshold,
                "listen_timeout": self.listen_timeout,
                "whisper_cpu_threads": self.whisper_cpu_threads,
                "whisper_compute_type": self.whisper_compute_type,
                "beam_size": self.beam_size,
                "vad_filter": self.vad_filter,
            },
            "LanguageModel": {
                "inference_engine": self.inference_engine,
                "tokenizer_type": self.tokenizer_type,
                "maximum_local_tokens": self.maximum_local_tokens,
                "max_response_sentences": self.max_response_sentences,
                "wait_time_buffer": self.wait_time_buffer,
                "same_output_limit": self.same_output_limit,
                "conversation_limit_pct": self.conversation_limit_pct,
                "min_conversation_length": self.min_conversation_length,
                "reload_buffer": self.reload_buffer,
                # "reload_wait_time": self.reload_wait_time,
            },
            "PromptStyle":{
                "prompt_style": self.prompt_style,
                "behavior_style": self.behavior_style,
                "conversation_start_type": self.conversation_start_type,
                "strip_smalls": self.strip_smalls,
                "small_size": self.small_size,
                "assure_grammar": self.assure_grammar,
                "assist_check": self.assist_check,
                "as_a_check": self.as_a_check,
                "break_on_time_announcements": self.break_on_time_announcements,
                "meet_string_game_events": self.meet_string_game_events,
                "conversation_start_role": self.conversation_start_role,
                "custom_possible_player_aliases": self.custom_possible_player_aliases,
            },
            "InferenceOptions": {
                "temperature": self.temperature,
                "top_p": self.top_p,
                "min_p": self.min_p,
                "typical_p": self.typical_p,
                "top_k": self.top_k,
                "repeat_penalty": self.repeat_penalty,
                "tfs_z": self.tfs_z,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
                "mirostat_mode": self.mirostat_mode,
                "mirostat_eta": self.mirostat_eta,
                "mirostat_tau": self.mirostat_tau,
                "max_tokens": self.max_tokens,
            },
            "openai_api": {
                "llm": self.llm,
                "alternative_openai_api_base": self.alternative_openai_api_base,
                "secret_key_file_path": self.secret_key_file_path,
                "banned_samplers": self.banned_samplers,
            },
            "llama_cpp_python": {
                "model_path": self.model_path,
                "n_gpu_layers": self.n_gpu_layers,
                "n_threads": self.n_threads,
                "n_batch": self.n_batch,
                "tensor_split": self.tensor_split,
                "main_gpu": self.main_gpu,
                "split_mode": self.split_mode,
                "use_mmap": self.use_mmap,
                "use_mlock": self.use_mlock,
                "n_threads_batch": self.n_threads_batch,
                "offload_kqv": self.offload_kqv,
            },
            "llava_cpp_python": {
                "llava_clip_model_path": self.llava_clip_model_path,
                "ocr_lang": self.ocr_lang,
                "ocr_use_angle_cls": self.ocr_use_angle_cls,
                "ocr_filter": self.ocr_filter,
                "append_system_image_near_end": self.append_system_image_near_end,
                "llava_image_message_depth": self.llava_image_message_depth,
                "llava_image_message": self.llava_image_message,
                "paddle_ocr": self.paddle_ocr,
                "ocr_resolution": self.ocr_resolution,
                "clip_resolution": self.clip_resolution,
            },
            "transformers": {
                "transformers_model_slug": self.transformers_model_slug,
                "trust_remote_code": self.trust_remote_code,
                "device_map": self.device_map,
                "load_in_8bit": self.load_in_8bit,
            },
            "Speech": {
                "tts_engine": self.tts_engine,
                "end_conversation_wait_time": self.end_conversation_wait_time,
                "sentences_per_voiceline": self.sentences_per_voiceline,
                "narrator_voice": self.narrator_voice,
                "narrator_volume": self.narrator_volume,
                "narrator_delay": self.narrator_delay,
            },
            "xVASynth": {
                "xvasynth_path": self.xvasynth_path,
                "xvasynth_process_device": self.xvasynth_process_device,
                "pace": self.pace,
                "use_cleanup":self.use_cleanup,
                "use_sr": self.use_sr,
                "xvasynth_base_url": self.xvasynth_base_url,
            },
            "xTTS": {
                "xtts_device": self.xtts_device,
                "xtts_voice_samples_dir": self.xtts_voice_samples_dir,
                "xtts_preload_latents": self.xtts_preload_latents,
                "xtts_use_cached_latents": self.xtts_use_cached_latents,
                "xtts_temperature": self.xtts_temperature,
                "xtts_top_k": self.xtts_top_k,
                "xtts_top_p": self.xtts_top_p,
                "xtts_length_penalty": self.xtts_length_penalty,
                "xtts_repetition_penalty": self.xtts_repetition_penalty,
                "xtts_speed": self.xtts_speed,
                "xtts_num_beams": self.xtts_num_beams,
            },
            "xTTS_api": {
                "xtts_api_base_url": self.xtts_api_base_url,
                "xtts_api_data": self.xtts_api_data,
                "default_xtts_api_model": self.default_xtts_api_model,
            },
            "Debugging": {
                "debug_mode": self.debug_mode,
                "share_debug_ui": self.share_debug_ui,
                "remove_mei_folders": self.remove_mei_folders,
                "play_audio_from_script": self.play_audio_from_script,
                "debug_character_name": self.debug_character_name,
                "debug_use_mic": self.debug_use_mic,
                "default_player_response": self.default_player_response,
                "add_voicelines_to_all_voice_folders": self.add_voicelines_to_all_voice_folders,
            },
            "Errors": {
                "continue_on_voice_model_error": self.continue_on_voice_model_error,
                "continue_on_missing_character": self.continue_on_missing_character,
                "continue_on_llm_api_error": self.continue_on_llm_api_error,
                "bad_author_retries": self.bad_author_retries,
                "retries": self.retries,
                "system_loop": self.system_loop,
            },
            "Config": {
                "linux_mode": self.linux_mode,
                "character_database_file": self.character_database_file,
                "conversation_data_directory": self.conversation_data_directory,
                "voice_model_ref_ids_file": self.voice_model_ref_ids_file,
                "logging_file_path": self.logging_file_path,
                "port": self.port,
            }
        }
    
    def default_types(self):
        typesobj = {}
        default = self.default()
        for key in default:
            typesobj[key] = {}
            for sub_key in default[key]:
                text = str(type(default[key][sub_key]))
                text = text.split("'")[1]
                typesobj[key][sub_key] = text
        return typesobj
    
    def host_config_server(self):
        self.config_server_app = flask.Flask(__name__)
        @self.config_server_app.route('/config', methods=['GET'])
        def get_config():
            export = self.export()
            print(export)
            return flask.jsonify(export)
        @self.config_server_app.route('/config', methods=['POST'])
        def post_config():
            data = flask.request.json
            for key in data:
                for sub_key in data[key]:
                    setattr(self, sub_key, data[key][sub_key])
            self.save()
            self.conversation_manager.restart = True
            if not self.conversation_manager.in_conversation:
                logging.info("Config updated and conversation manager not in a conversation. Restart the conversation manager to apply the new settings. - WILL BE FIXED IN FUTURE RELEASE")
            return flask.jsonify(self.export())
        @self.config_server_app.route('/defaults', methods=['GET'])
        def get_default():
            print(self.default())
            print(self.default_types())
            print(self.descriptions())
            return flask.jsonify({
                "defaultConfig": self.default(),
                "types": self.default_types(),
                "descriptions": self.descriptions()
            })
        @self.config_server_app.route('/', methods=['GET'])
        def index(): # Return the index.html file
            return flask.send_file('../webconfigurator/index.html')
        @self.config_server_app.route('/jquery-3.7.1.min.js', methods=['GET'])
        def jquery():
            return flask.send_file('../webconfigurator/jquery-3.7.1.min.js')
        self.config_server_app.run(port=self.port, threaded=True)
        logging.info(f"Config server running on port http://localhost:{self.port}/")
