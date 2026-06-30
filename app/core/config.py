from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_api_key: str = "EMPTY"
    vllm_model: str = "default"

    proxy_host: str = "0.0.0.0"
    proxy_port: int = 8080

    workspace_dir: str = "/home/ubuntu/workspace"

    dangerous_tools: list[str] = [
        "shell_execute",
        "file_write",
        "file_edit",
        "file_delete",
        "run_tests",
    ]

    require_approval: bool = True
    max_agent_iterations: int = 25

    class Config:
        env_file = ".env"
        env_prefix = "AGENT_"


settings = Settings()
