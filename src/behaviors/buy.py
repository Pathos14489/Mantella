from src.logging import logging
import src.behaviors.base_behavior as base_behavior

class buy(base_behavior.BaseBehavior):
    def __init__(self, manager):
        super().__init__(manager)
        self.keyword = "Buy"
        self.description = "If {perspective_player_name} wants to sell something to {name}, and {name} wants to buy something, to start the barter interaction, {name} will begin their sentence with 'Buy:'."
        # self.example = "'Hey, can I sell you something?' 'Buy: Sure, what do you have?'"
        self.examples = [
            [
                {
                    "role": "user",
                    "name": "Nazeem",
                    "content":"Hey, can I sell you something?"
                },
                {
                    "role": "assistant",
                    "content":"{command} Sure, what do you have?"
                },
            ]
        ]
        self.activation_sentences = []
        self.valid_games = ["skyrim","skyrimvr"]
    
    def run(self, speaker_character=None, sentence=None):
        logging.info(f"{speaker_character.name} wants to buy something from the {self.manager.conversation_manager.player_name}.")
        self.queue_actor_method(speaker_character,"Wait","2")
        self.new_game_event(f"{speaker_character.name} began buying something from {self.manager.conversation_manager.player_name}.")
        self.queue_actor_method(speaker_character,"OpenBarterMenu")
