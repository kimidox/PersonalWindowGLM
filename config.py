def get_config(key:str):
    import dotenv

    dotenv.load_dotenv()
    return dotenv.get_key(dotenv_path=".env.dev",key_to_get=key)

OPENAI_API_KEY = get_config("OPENAI_API_KEY")
OPENAI_BASE_URL = get_config("OPENAI_BASE_URL")
MODEL_NAME = get_config("MODEL_NAME")
MAX_ITERATIONS = 20



