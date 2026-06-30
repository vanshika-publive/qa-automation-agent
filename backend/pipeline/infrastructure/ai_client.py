import os
from openai import OpenAI

from pipeline.constants import AI_MODEL
class AiClientFactory:

    @staticmethod
    def create() -> dict:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError(
                'Missing credential: OPENAI_API_KEY\n'
                'Set it in .env (local dev) or environment variables.'
            )
        return {'client': OpenAI(api_key=api_key), 
                'model': AI_MODEL}