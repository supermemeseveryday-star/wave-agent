# Wave Agent MVP architecture

User → FastAPI / UI → WaveMasterAgent → WorldModel retrieval → deterministic tool or Qwen provider → QwenJudge rules → experience → verified training candidate → dataset.

The model provider supports Ollama and OpenAI-compatible chat endpoints. The latter can connect to Qwen cloud, OpenAI, Anthropic or Google only through a compatible gateway. Native provider adapters, embeddings, vision, browser/computer control, asynchronous workers, scheduler, and model training are future integrations, not claimed as implemented.

World records share a versioned schema with kinds for knowledge, principles, causal edges, states, predictions, experiences, skills and workflows. Retrieval is keyword based in this MVP. A quantitative causal edge needs `cause`, `effect` and `coefficient`; without it, predictions return unchanged state with high uncertainty. This is a scenario calculation, not a calibrated probabilistic forecast.

Tool execution is allowlisted. Arithmetic and clock are deterministic. Network fetch requires explicit `READ_NETWORK` permission, HTTPS and public DNS. No shell, write, send, purchase or publish tool is exposed. Judge verification currently trusts deterministic tool output only; model-generated facts are retained as experience with unverified status. Dataset generation filters for verified, high-score, deduplicated examples. An offline candidate must pass every benchmark dimension before acceptance; there is no automatic production replacement.

Manual `/learn` entries for knowledge, principles and causality are labeled `user_provided` and capped at 0.5 confidence. They can inform reasoning and scenarios, but do not become verified training data. The local API has no authentication; Compose binds all published ports to loopback and should not be exposed to other hosts without an auth layer.
