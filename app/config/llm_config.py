import yaml
from pydantic import BaseModel, Field
from typing import Optional # Import Optional
from config.app_config import PROJECT_ROOT

import os
class LLMSettings(BaseModel):
    model: str = Field(..., description="Model name")
    base_url: str = Field(..., description="API base URL")
    api_key: str = Field(..., description="API key")
    max_tokens: int = Field(4096, description="Maximum number of tokens per request")
    temperature: float = Field(1.0, description="Sampling temperature")
    api_type: str = Field(..., description="AzureOpenai or Openai")
    # Make api_version optional if it's not always required
    api_version: Optional[str] = Field(None, description="Azure Openai version if AzureOpenai")

def load_config_from_yaml(path: str = os.path.join(PROJECT_ROOT, "config.yaml")) -> LLMSettings:
    try:
        with open(path, 'r') as f:
            config_data = yaml.safe_load(f)
        if config_data is None:
             raise ValueError(f"Config file '{path}' is empty or invalid.")
        # Pydantic automatically validates when creating the instance
        settings = LLMSettings(**config_data)
        return settings
    except FileNotFoundError:
        print(f"Error: Configuration file '{path}' not found.")
        raise
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{path}': {e}")
        raise
    except Exception as e: # Catch Pydantic validation errors too
        print(f"Error loading or validating configuration: {e}")
        raise

llm_settings = load_config_from_yaml()

