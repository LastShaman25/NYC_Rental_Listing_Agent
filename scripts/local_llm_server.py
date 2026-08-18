"""Minimal OpenAI-compatible chat server for the RentAgent post Studio.

Runs under the Innerfy/MVP venv's python, which has ``llama_cpp`` installed
(the full ``llama_cpp.server`` extra is not present there, so this wrapper
uses only the standard library). Exposes exactly what the Studio needs:

- ``GET  /v1/models``           -> model listing (used as a readiness probe)
- ``POST /v1/chat/completions`` -> non-streaming chat completion

``llama_cpp.Llama.create_chat_completion`` already returns the OpenAI response
shape, so the payload passes straight through. Binds to 127.0.0.1 only.

Usage: python local_llm_server.py <model.gguf> <port>
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

MODEL_ALIAS = "qwen2.5-7b-instruct"


def main() -> None:
    """Pure-GPU inference (owner decision 2026-08-18: never CPU).

    All layers are offloaded (n_gpu_layers=-1). If the installed llama.cpp
    build cannot offload to the GPU, the server refuses to start rather than
    silently degrading to CPU. Verified on the RTX 5070 Ti: full offload,
    ~100 tok/s eval.
    """
    model_path, port = sys.argv[1], int(sys.argv[2])
    from llama_cpp import Llama, llama_supports_gpu_offload

    if not llama_supports_gpu_offload():
        print(
            "FATAL: this llama.cpp build has no GPU offload support — refusing to "
            "run on CPU (owner requires pure GPU inference).",
            flush=True,
        )
        sys.exit(1)
    print(f"Loading {model_path} onto the GPU (all layers)...", flush=True)
    llm = Llama(model_path=model_path, n_ctx=8192, n_gpu_layers=-1, verbose=False)
    print(f"Model loaded. Serving http://127.0.0.1:{port}/v1", flush=True)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"[llm] {fmt % args}", flush=True)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path in ("/v1/models", "/health", "/healthz"):
                self._send(200, {"object": "list", "data": [{"id": MODEL_ALIAS}]})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path != "/v1/chat/completions":
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length))
                result = llm.create_chat_completion(
                    messages=request["messages"],
                    temperature=float(request.get("temperature", 0.7)),
                    max_tokens=int(request.get("max_tokens", 600)),
                )
                self._send(200, result)
            except Exception as exc:  # surfaced to the Studio's error card
                self._send(500, {"error": {"message": f"{type(exc).__name__}: {exc}"}})

    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
