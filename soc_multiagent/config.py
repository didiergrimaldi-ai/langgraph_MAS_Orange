import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys principales
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY")
    
    # Gmail Configuration
    GMAIL_CREDENTIALS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN")
    
    # SOC Email Configuration
    SOC_EMAIL_RECIPIENT = os.getenv("SOC_EMAIL_RECIPIENT")
    SOC_EMAIL_SENDER = os.getenv("SOC_EMAIL_SENDER")
    
    # Validación de configuración crítica
    @classmethod
    def validate_required_config(cls):
        required_keys = [
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("TAVILY_API_KEY", cls.TAVILY_API_KEY),
            ("VIRUSTOTAL_API_KEY", cls.VIRUSTOTAL_API_KEY),
            ("SOC_EMAIL_RECIPIENT", cls.SOC_EMAIL_RECIPIENT)
        ]
       
        missing_keys = [key for key, value in required_keys if not value]

        if missing_keys:
            raise ValueError(f"Faltan las siguientes variables de entorno: {', '.join(missing_keys)}")
        
        return True
    
config = Config()