from .openai_handler import OpenAIHandler

class DeepseekHandler(OpenAIHandler):
    key = "deepseek"
    default_models = (("deepseek-chat", "deepseek-chat"),("deepseek-reasoner", "deepseek-reasoner") )
    def __init__(self, settings, path):
        super().__init__(settings, path)
        self.set_setting("endpoint", "https://api.deepseek.com")
        self.set_setting("advanced_params", False)

    def supports_vision(self) -> bool:
        return False 

    def get_extra_settings(self) -> list:
        return self.build_extra_settings("Deepseek", True, True, False, False, True, None, "https://api-docs.deepseek.com/quick_start/pricing", False, True)

