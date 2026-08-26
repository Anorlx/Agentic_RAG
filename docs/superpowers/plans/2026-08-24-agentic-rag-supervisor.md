# Agentic RAG Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a LangGraph supervisor that routes rice-agriculture questions to direct LLM answering, the existing knowledge-base RAG graph, Tavily web search, or both tools in parallel, and expose its observable route and sources in the chat UI.

**Architecture:** Keep `backend/rag/pipeline.py` as the unchanged RAG subgraph.  Add a focused outer graph in `backend/chat/supervisor.py`: it reads project-level `AGENTS.md`, asks the configured model for a strictly validated route decision, uses `Send` to fan out the dual-tool path, and synthesizes one answer from typed RAG and web evidence.  `chat/service.py` invokes this graph and forwards its safe execution events through the existing SSE and persisted `rag_trace` contracts.

**Tech Stack:** Python 3.12, LangGraph `StateGraph`/`Send`, LangChain OpenAI chat models, Tavily Python client, FastAPI SSE, Pydantic v2, Vue 3, Pinia, Vitest, unittest.

---

## File structure

- Create `AGENTS.md`: fixed, human-editable description of the rice-agriculture knowledge base and the routing policy; it is read on every request.
- Create `backend/chat/supervisor.py`: all outer-graph state, Pydantic route/source contracts, routing, RAG invocation, Tavily normalization, synthesis, and safe event emission.
- Modify `backend/chat/runtime.py`: provide a non-tool-bound structured router model and an answer model to the supervisor; remove the old outer LangChain tool-selection factory once callers have migrated.
- Modify `backend/chat/service.py`: invoke the supervisor for normal turns, preserve existing HITL continuation, preserve streaming and message persistence, and surface the supervisor trace.
- Modify `backend/chat/request_context.py`: allow the supervisor to store a final combined trace without changing RAG tool-budget behavior.
- Modify `backend/schemas/chat.py`: model and normalize supervisor route metadata and typed web sources while remaining backward-compatible with stored RAG traces.
- Modify `pyproject.toml`: add the `tavily-python` runtime dependency.
- Modify `frontend/src/types/chat.ts`: mirror the backend web-source and supervisor-trace contracts.
- Modify `frontend/src/components/Chat/References.vue`: render separate knowledge-base and web-source cards with title, domain, excerpt, and a safe external link.
- Modify `frontend/src/components/Chat/MessageItem.vue`: show a concise route summary and combined source count without displaying private reasoning.
- Modify `frontend/src/assets/styles/main.css`: style route badges and web-source cards using the existing source-card visual language.
- Create `tests/test_agentic_rag_supervisor.py`: unit tests for all routes, dual-path fan-out/join, RAG propagation, web source normalization, and failure fallback.
- Modify `tests/test_rag_trace_schema.py`: verify the expanded trace accepts only intended route and web-source fields and drops unknown input.
- Modify `frontend/src/stores/chat.spec.ts` or create `frontend/src/components/Chat/References.spec.ts`: verify trace events and web sources are retained and displayed.

### Task 1: Establish the routing policy and dependency contract

**Files:**
- Create: `AGENTS.md`
- Modify: `pyproject.toml`
- Test: `tests/test_agentic_rag_supervisor.py`

- [ ] **Step 1: Write failing profile and config tests**

```python
from pathlib import Path
import unittest

from backend.chat.supervisor import load_agent_profile


class SupervisorProfileTests(unittest.TestCase):
    def test_agent_profile_is_loaded_from_project_root_for_each_call(self):
        profile = load_agent_profile()
        self.assertIn("水稻", profile)
        self.assertIn("Tavily", profile)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor.SupervisorProfileTests -v`

Expected: FAIL because `backend.chat.supervisor` does not yet exist.

- [ ] **Step 3: Add the editable rice-agriculture profile and Tavily dependency**

Create `AGENTS.md` with these binding rules: the KB covers rice cultivation, varieties, breeding, pests/disease, soil/fertilizer, water management, machinery, and uploaded material; it is preferred for uploaded-specific evidence, protocols, measurements, and document citations; current policy, news, market price, outbreak, and current research use web; unrelated/general stable questions should normally answer directly.  Add `"tavily-python>=0.7.0"` to the main dependency list in `pyproject.toml`.

```python
# backend/chat/supervisor.py
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def load_agent_profile() -> str:
    return (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8").strip()
```

- [ ] **Step 4: Install the declared dependency into the existing environment**

Run: `conda run -n Agentrag pip install -e .`

Expected: installation finishes with `Successfully installed tavily-python` or confirms it is already satisfied; it must not download embedding or reranker models.

- [ ] **Step 5: Run the profile test to verify it passes**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor.SupervisorProfileTests -v`

Expected: PASS.

- [ ] **Step 6: Commit the isolated contract change**

```bash
git add AGENTS.md pyproject.toml tests/test_agentic_rag_supervisor.py
git commit -m "feat: define rice knowledge-base routing profile"
```

### Task 2: Build typed routing and source contracts

**Files:**
- Create: `backend/chat/supervisor.py`
- Modify: `backend/schemas/chat.py`
- Modify: `tests/test_rag_trace_schema.py`
- Test: `tests/test_agentic_rag_supervisor.py`

- [ ] **Step 1: Write failing routing and trace-schema tests**

```python
def test_route_decision_accepts_only_the_four_supervisor_routes(self):
    self.assertEqual(
        "knowledge_base_and_web_search",
        RouteDecision.model_validate({
            "route": "knowledge_base_and_web_search",
            "reason": "需要知识库证据和当前公开信息",
        }).route,
    )
    with self.assertRaises(ValidationError):
        RouteDecision.model_validate({"route": "anything", "reason": "x"})

def test_trace_normalizes_web_sources_and_removes_unknown_fields(self):
    trace = normalize_rag_trace({
        "supervisor_route": "web_search",
        "web_sources": [{"title": "稻米资讯", "url": "https://example.com/a", "domain": "example.com", "snippet": "摘要", "ignored": 1}],
        "ignored": True,
    })
    self.assertEqual("web_search", trace["supervisor_route"])
    self.assertEqual(["稻米资讯"], [item["title"] for item in trace["web_sources"]])
    self.assertNotIn("ignored", trace)
```

- [ ] **Step 2: Run the selected tests to verify they fail**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor tests.test_rag_trace_schema -v`

Expected: FAIL because `RouteDecision`, `WebSource`, and supervisor trace fields are absent.

- [ ] **Step 3: Add strict contracts and backward-compatible trace normalization**

Define these types in `backend/chat/supervisor.py`:

```python
class RouteDecision(BaseModel):
    route: Literal["direct", "knowledge_base", "web_search", "knowledge_base_and_web_search"]
    reason: str = Field(min_length=1, max_length=240)
    needs_current_information: bool = False
    needs_citations: bool = False

class WebSource(BaseModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    snippet: str = ""
    score: float | None = None
    published_date: str | None = None
```

Add matching `WebSource` plus optional `supervisor_route`, `supervisor_reason`, `web_search_status`, `web_search_error`, and `web_sources` fields to `RagTraceFields`.  Normalize every web source through the strict schema, discard malformed URLs/unknown keys, and leave older RAG-only traces valid.

- [ ] **Step 4: Run the selected tests to verify they pass**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor tests.test_rag_trace_schema -v`

Expected: PASS.

- [ ] **Step 5: Commit the contract layer**

```bash
git add backend/chat/supervisor.py backend/schemas/chat.py tests/test_agentic_rag_supervisor.py tests/test_rag_trace_schema.py
git commit -m "feat: add supervisor route and web source contracts"
```

### Task 3: Implement graph routing and safe observable events

**Files:**
- Modify: `backend/chat/supervisor.py`
- Modify: `backend/chat/runtime.py`
- Test: `tests/test_agentic_rag_supervisor.py`

- [ ] **Step 1: Write failing deterministic graph tests**

```python
def test_router_selects_each_of_the_four_conditional_edges(self):
    for route, expected in {
        "direct": "direct_answer",
        "knowledge_base": "knowledge_base_tool",
        "web_search": "web_search_tool",
        "knowledge_base_and_web_search": "parallel_tools",
    }.items():
        self.assertEqual(expected, route_after_decision({"route_decision": RouteDecision(route=route, reason="test")}))

def test_parallel_route_emits_one_send_per_tool(self):
    sends = parallel_tool_sends({"question": "当前水稻价格", "route_decision": RouteDecision(route="knowledge_base_and_web_search", reason="test")})
    self.assertEqual({"knowledge_base_tool", "web_search_tool"}, {send.node for send in sends})
```

- [ ] **Step 2: Run the graph tests to verify they fail**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor.SupervisorRoutingTests -v`

Expected: FAIL because graph edge functions are not yet implemented.

- [ ] **Step 3: Implement a `StateGraph` without duplicating RAG internals**

Use `TypedDict` state with `question`, `conversation`, `agent_profile`, `route_decision`, `rag_result`, `web_result`, `execution_events`, `answer`, and `rag_trace`.  Make list-valued parallel fields use `operator.add`.  Implement the following node responsibilities:

```python
graph = StateGraph(SupervisorState)
graph.add_node("load_agent_profile", load_profile_node)
graph.add_node("route_request", route_request_node)
graph.add_node("direct_answer", direct_answer_node)
graph.add_node("knowledge_base_tool", knowledge_base_tool_node)
graph.add_node("web_search_tool", web_search_tool_node)
graph.add_node("answer_synthesis", answer_synthesis_node)
graph.add_node("build_execution_trace", build_execution_trace_node)
graph.add_edge(START, "load_agent_profile")
graph.add_edge("load_agent_profile", "route_request")
graph.add_conditional_edges("route_request", route_after_decision, {
    "direct_answer": "direct_answer",
    "knowledge_base_tool": "knowledge_base_tool",
    "web_search_tool": "web_search_tool",
    "parallel_tools": "parallel_tools",
})
graph.add_conditional_edges("parallel_tools", parallel_tool_sends, ["knowledge_base_tool", "web_search_tool"])
for node in ("direct_answer", "knowledge_base_tool", "web_search_tool"):
    graph.add_edge(node, "answer_synthesis")
graph.add_edge("answer_synthesis", "build_execution_trace")
graph.add_edge("build_execution_trace", END)
```

`route_request_node` must use structured output with `RouteDecision`, append only a safe route event such as `("🧭", "已选择知识库与网页联合回答", decision.reason)`, and fall back to `direct` with a safe reason if routing-model parsing fails.  `knowledge_base_tool_node` imports and invokes the existing `run_rag_graph(question, ctx)` and returns its result unchanged in state.  Never include prompts, model token traces, or chain-of-thought in `execution_events`.

Expose `router_model` and `answer_model` from `runtime.py` using the existing `MODEL`, `FAST_MODEL`, `BASE_URL`, and `ARK_API_KEY` configuration.  Do not alter the configured local embedding/reranker settings.

- [ ] **Step 4: Run graph tests to verify they pass**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor.SupervisorRoutingTests -v`

Expected: PASS for all four routes and the two `Send` fan-out branches.

- [ ] **Step 5: Commit the LangGraph routing graph**

```bash
git add backend/chat/supervisor.py backend/chat/runtime.py tests/test_agentic_rag_supervisor.py
git commit -m "feat: route agent requests with LangGraph"
```

### Task 4: Add Tavily execution, normalization, and answer synthesis

**Files:**
- Modify: `backend/chat/supervisor.py`
- Test: `tests/test_agentic_rag_supervisor.py`

- [ ] **Step 1: Write failing Tavily and fallback tests**

```python
def test_tavily_result_is_normalized_to_display_safe_web_sources(self):
    sources = normalize_tavily_results({"results": [{"title": "Rice bulletin", "url": "https://news.example.org/rice", "content": "New guidance", "score": 0.8}]})
    self.assertEqual("Rice bulletin", sources[0].title)
    self.assertEqual("news.example.org", sources[0].domain)
    self.assertEqual("New guidance", sources[0].snippet)

def test_web_failure_keeps_rag_evidence_available_for_synthesis(self):
    state = web_search_failure_state("service unavailable")
    self.assertEqual("failed", state["web_result"]["status"])
    self.assertIn("网页搜索暂时不可用", state["execution_events"][0]["label"])
```

- [ ] **Step 2: Run the Tavily tests to verify they fail**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor.TavilyTests -v`

Expected: FAIL because Tavily normalization and failure state are absent.

- [ ] **Step 3: Implement the web node and synthesis behavior**

Use the configured `TAVILY_API_KEY`, and call the client only inside `web_search_tool_node`:

```python
from tavily import TavilyClient

response = TavilyClient(api_key=api_key).search(
    query=state["question"],
    search_depth="advanced",
    max_results=5,
)
sources = normalize_tavily_results(response)
```

Normalize title/URL/content/score/published date, derive the URL hostname via `urllib.parse.urlparse`, discard non-HTTP(S) or incomplete entries, and cap source snippets to 600 characters.  Emit only `开始检索公开网页`, `网页检索完成（N 个来源）`, or `网页搜索暂时不可用` events.  With an absent key, do not call the provider; return a failed web result and allow synthesis to continue.

Synthesis rules: direct route answers normally; RAG-only uses retrieved chunks and preserves inline `[1]` citation instructions; web-only cites sources as `[W1]`, `[W2]`; combined route clearly separates/uses both source labels and states when either tool failed or found no reliable evidence.  If RAG returns a HITL status, bypass normal synthesis and preserve the existing status/trace for `chat/service.py` to request the user’s clarification.

- [ ] **Step 4: Run the Tavily tests to verify they pass**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor.TavilyTests -v`

Expected: PASS without a network call; tests must inject a fake Tavily client.

- [ ] **Step 5: Commit web search and synthesis**

```bash
git add backend/chat/supervisor.py tests/test_agentic_rag_supervisor.py
git commit -m "feat: add Tavily search to agentic RAG supervisor"
```

### Task 5: Migrate synchronous and SSE chat execution to the supervisor

**Files:**
- Modify: `backend/chat/service.py`
- Modify: `backend/chat/request_context.py`
- Modify: `backend/chat/runtime.py`
- Test: `tests/test_chat_hitl_resume.py`
- Test: `tests/test_request_context_di.py`

- [ ] **Step 1: Write failing service integration tests**

```python
@patch("backend.chat.service.run_supervisor")
def test_normal_chat_uses_supervisor_and_persists_combined_trace(self, run_supervisor):
    run_supervisor.return_value = {"answer": "回答", "rag_trace": {"supervisor_route": "web_search", "web_sources": []}}
    result = chat_with_agent("查询最新水稻政策", user_id="u", session_id="s")
    self.assertEqual("回答", result["response"])
    self.assertEqual("web_search", result["rag_trace"]["supervisor_route"])
```

- [ ] **Step 2: Run service and HITL tests to verify the new integration test fails**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor tests.test_chat_hitl_resume tests.test_request_context_di -v`

Expected: FAIL because normal chat still builds `create_agent_for_request`.

- [ ] **Step 3: Replace only the normal-turn outer agent path**

In both `chat_with_agent` and `chat_with_agent_stream`, retain current storage, context-message construction, first-title emission, cancellation, HITL-resume flow, and persistent-note update.  Replace only the normal turn’s `create_agent_for_request(...)` invocation with `run_supervisor(...)` / an executor-backed call.  Pass `effective_user_text`, `context_messages`, and `ctx`; forward supervisor events through `ctx.emit_rag_step`; stream the final synthesis answer only after the safe tool events.  Store the supervisor’s combined normalized trace so existing session history APIs continue to return one `rag_trace` per assistant message.

Keep `_is_hitl_trace()` and its existing pending-state workflow.  Ensure dual-route RAG HITL returns the clarification before a speculative web-only answer.

- [ ] **Step 4: Run integration and regression tests to verify they pass**

Run: `conda run -n Agentrag python -m unittest tests.test_agentic_rag_supervisor tests.test_chat_hitl_resume tests.test_request_context_di tests.test_rag_trace_schema -v`

Expected: PASS; no existing HITL or request-context tests regress.

- [ ] **Step 5: Commit service migration**

```bash
git add backend/chat/service.py backend/chat/request_context.py backend/chat/runtime.py tests/test_agentic_rag_supervisor.py
git commit -m "feat: run chat requests through agentic RAG supervisor"
```

### Task 6: Display route and web sources in the frontend

**Files:**
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/components/Chat/References.vue`
- Modify: `frontend/src/components/Chat/MessageItem.vue`
- Modify: `frontend/src/assets/styles/main.css`
- Test: `frontend/src/stores/chat.spec.ts`

- [ ] **Step 1: Write failing frontend contract tests**

```ts
it('keeps supervisor web sources from a trace SSE event', () => {
  const trace = {
    supervisor_route: 'web_search',
    supervisor_reason: '需要当前公开信息',
    web_sources: [{ title: 'Rice bulletin', domain: 'example.org', url: 'https://example.org/rice', snippet: 'Current update' }],
  };
  expect(trace.web_sources[0].domain).toBe('example.org');
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `npm run test -- --run`

Expected: FAIL type-check/compile because `RagTrace` does not yet declare supervisor and web-source fields.

- [ ] **Step 3: Add display-safe types and components**

Add `WebSource` to `frontend/src/types/chat.ts` and optional `supervisor_route`, `supervisor_reason`, `web_search_status`, `web_search_error`, `web_sources` to `RagTraceFields`.

In `MessageItem.vue`, show a compact badge under the assistant name only when `supervisor_route` is present.  Map the route values to Chinese labels: `直接回答`, `知识库检索`, `网页搜索`, and `知识库 + 网页搜索`.  Use `supervisor_reason` exactly as an observable explanation, never label it “thinking”.

In `References.vue`, keep current knowledge-base citations under `知识库来源`; add a second details block `网页来源` when `web_sources.length > 0`.  Render this structure for each source:

```vue
<a class="web-source-link" :href="source.url" target="_blank" rel="noopener noreferrer">
  <span class="source-file"><i class="fa-solid fa-globe"></i>{{ source.title }}</span>
  <span class="source-domain">{{ source.domain }}</span>
</a>
<div v-if="source.snippet" class="source-excerpt">{{ source.snippet }}</div>
```

Use existing `references-*` classes plus narrowly scoped additions for badge/domain/link contrast.  Do not render web URLs as raw HTML, do not create a “thought process” panel, and do not change existing citation-click behavior.

- [ ] **Step 4: Run tests and production build to verify they pass**

Run: `npm run test -- --run && npm run build`

Expected: all frontend tests pass and Vite emits `dist/` successfully.

- [ ] **Step 5: Commit the UI work**

```bash
git add frontend/src/types/chat.ts frontend/src/components/Chat/References.vue frontend/src/components/Chat/MessageItem.vue frontend/src/assets/styles/main.css frontend/src/stores/chat.spec.ts
git commit -m "feat: show supervisor route and web sources"
```

### Task 7: Validate the integrated application without downloading models

**Files:**
- Modify: `tests/test_agentic_rag_supervisor.py`
- Modify: `README.md` only if an existing configuration section needs `TAVILY_API_KEY` documented without revealing a value

- [ ] **Step 1: Add final regression coverage for route-to-trace behavior**

```python
def test_combined_route_trace_contains_rag_and_web_source_sections(self):
    trace = build_execution_trace_node({
        "route_decision": RouteDecision(route="knowledge_base_and_web_search", reason="需要知识库证据和当前公开信息"),
        "rag_result": {"rag_trace": {"retrieved_chunks": [{"filename": "rice.pdf"}]}},
        "web_result": {"status": "completed", "sources": [WebSource(title="News", url="https://example.com", domain="example.com")]},
    })["rag_trace"]
    self.assertEqual("knowledge_base_and_web_search", trace["supervisor_route"])
    self.assertEqual("rice.pdf", trace["retrieved_chunks"][0]["filename"])
    self.assertEqual("News", trace["web_sources"][0]["title"])
```

- [ ] **Step 2: Run backend and frontend full suites**

Run: `conda run -n Agentrag python -m unittest discover -s tests -v`

Expected: all backend tests pass, including current local-reranker tests.

Run: `npm run test -- --run && npm run build`

Expected: all frontend tests pass and build succeeds.

- [ ] **Step 3: Start the service in the existing `Agentrag` environment and make safe route checks**

Run: `conda run -n Agentrag uvicorn backend.app:app --host 127.0.0.1 --port 8000`

Expected: application starts without loading/downloading the local embedding model at process startup.

Use authenticated local UI/API requests to verify: a stable unrelated question yields `direct`; an uploaded-document question yields `knowledge_base`; a current rice-policy/market question yields `web_search`; and a request for current interpretation of uploaded material yields the combined route.  Confirm stream steps show route/tool events and answers show only sources—not hidden reasoning.

- [ ] **Step 4: Inspect the working tree and commit the validation/documentation changes**

Run: `git status --short`

Expected: only intended supervisor feature files are staged; preserve pre-existing local reranker and Docker changes.

```bash
git add tests/test_agentic_rag_supervisor.py README.md
git commit -m "test: verify agentic RAG route source integration"
```
