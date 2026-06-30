import argparse
import uvicorn
from app.core.config import settings


def main():
    parser = argparse.ArgumentParser(description="Dev Agent - Local AI coding proxy")
    parser.add_argument("--host", default=settings.proxy_host, help="Host to bind to")
    parser.add_argument("--port", type=int, default=settings.proxy_port, help="Port to bind to")
    parser.add_argument("--workspace", default=None, help="Workspace directory (overrides .env)")
    parser.add_argument("--vllm-url", default=None, help="vLLM base URL (overrides .env)")
    args = parser.parse_args()

    if args.workspace:
        settings.workspace_dir = args.workspace
    if args.vllm_url:
        settings.vllm_base_url = args.vllm_url

    print(f"Dev Agent starting...")
    print(f"  vLLM: {settings.vllm_base_url}")
    print(f"  Workspace: {settings.workspace_dir}")
    print(f"  Listening: http://{args.host}:{args.port}")
    print()

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
