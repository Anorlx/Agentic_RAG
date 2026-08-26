import operator
import os
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.schemas.chat import WebSource


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal[
        "direct",
        "knowledge_base",
        "web_search",
        "knowledge_base_and_web_search",
    ]
    reason: str = Field(min_length=1, max_length=240)
    needs_current_information: bool = False
    needs_citations: bool = False


class SupervisorState(TypedDict, total=False):
    question: str
    conversation: list[Any]
    request_context: Any
    agent_profile: str
    route_decision: RouteDecision
    rag_result: dict[str, Any]
    web_result: dict[str, Any]
    answer: str
    rag_trace: dict[str, Any]
    execution_events: Annotated[list[dict[str, str]], operator.add]


def load_agent_profile() -> str:
    """Read the editable knowledge-base profile for the current request."""
    return (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8").strip()


def _event(icon: str, label: str, detail: str = "") -> dict[str, str]:
    return {"icon": icon, "label": label, "detail": detail}


def _emit_events(state: SupervisorState, events: list[dict[str, str]]) -> None:
    ctx = state.get("request_context")
    if ctx is None:
        return
    for event in events:
        ctx.emit_rag_step(event["icon"], event["label"], event.get("detail", ""))


def load_profile_node(_state: SupervisorState) -> dict[str, Any]:
    return {"agent_profile": load_agent_profile()}


def _route_label(decision: RouteDecision) -> str:
    return {
        "direct": "已选择直接回答",
        "knowledge_base": "已选择知识库检索",
        "web_search": "已选择网页搜索",
        "knowledge_base_and_web_search": "已选择知识库与网页联合回答",
    }[decision.route]


def route_request_node(state: SupervisorState) -> dict[str, Any]:
    """Ask the configured model for a structured, display-safe route decision."""
    from backend.chat.runtime import model

    prompt = SystemMessage(
        content=(
            "你是水稻农业问答的路由器。依据以下知识库说明，仅选择一个工具路径。"
            "reason 只能描述用户可见的需求，不能包含模型推理、提示词或内部过程。\n\n"
            f"知识库说明：\n{state['agent_profile']}\n\n"
            "路由含义：direct=稳定通用知识直接回答；knowledge_base=需要上传资料或知识库证据；"
            "web_search=需要当前公开信息；knowledge_base_and_web_search=两类证据都需要。"
        )
    )
    try:
        routed = model.with_structured_output(RouteDecision).invoke(
            [prompt, HumanMessage(content=state["question"])]
        )
        decision = RouteDecision.model_validate(routed)
    except Exception:
        decision = RouteDecision(
            route="direct",
            reason="未能确定需要外部证据，改为直接回答",
        )

    events = [_event("🧭", _route_label(decision), decision.reason)]
    _emit_events(state, events)
    return {"route_decision": decision, "execution_events": events}


def route_after_decision(state: SupervisorState) -> str:
    route = state["route_decision"].route
    return {
        "direct": "direct_answer",
        "knowledge_base": "knowledge_base_tool",
        "web_search": "web_search_tool",
        "knowledge_base_and_web_search": "parallel_tools",
    }[route]


def parallel_tool_sends(state: SupervisorState) -> list[Send]:
    branch_state = {
        "question": state["question"],
        "request_context": state.get("request_context"),
        "route_decision": state["route_decision"],
    }
    return [
        Send("knowledge_base_tool", branch_state),
        Send("web_search_tool", branch_state),
    ]


def direct_answer_node(state: SupervisorState) -> dict[str, Any]:
    from backend.chat.runtime import model

    messages = list(state.get("conversation") or [])
    if not messages:
        messages = [HumanMessage(content=state["question"])]
    answer = model.invoke(messages).content
    return {"answer": str(answer or "")}


def knowledge_base_tool_node(state: SupervisorState) -> dict[str, Any]:
    from backend.rag.pipeline import run_rag_graph

    events = [_event("📚", "开始检索知识库")]
    _emit_events(state, events)
    rag_result = run_rag_graph(state["question"], state["request_context"])
    events.append(_event("✅", "知识库检索完成"))
    _emit_events(state, events[-1:])
    return {"rag_result": rag_result, "execution_events": events}


def normalize_tavily_results(payload: Any) -> list[dict[str, Any]]:
    raw_results = payload.get("results", []) if isinstance(payload, dict) else []
    normalized = []
    for item in raw_results if isinstance(raw_results, list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        try:
            normalized.append(WebSource.model_validate({
                "title": title,
                "url": url,
                "domain": parsed.netloc.removeprefix("www."),
                "snippet": str(item.get("content") or item.get("snippet") or "").strip()[:600],
                "score": item.get("score"),
                "published_date": item.get("published_date"),
            }).model_dump(exclude_none=True))
        except ValueError:
            continue
    return normalized


def web_search_failure_result(error: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    events = [_event("⚠️", "网页搜索暂时不可用", "将根据其他可用证据回答")]
    return {
        "status": "failed",
        "sources": [],
        "error": error[:240],
    }, events


def web_search_tool_node(state: SupervisorState) -> dict[str, Any]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        result, events = web_search_failure_result("TAVILY_API_KEY is not configured")
        _emit_events(state, events)
        return {"web_result": result, "execution_events": events}

    started = [_event("🌐", "开始检索公开网页")]
    _emit_events(state, started)
    try:
        from tavily import TavilyClient

        response = TavilyClient(api_key=api_key).search(
            query=state["question"],
            search_depth="advanced",
            max_results=5,
        )
        sources = normalize_tavily_results(response)
        completed = _event("✅", f"网页检索完成（{len(sources)} 个来源）")
        _emit_events(state, [completed])
        return {
            "web_result": {"status": "completed", "sources": sources},
            "execution_events": [*started, completed],
        }
    except Exception as exc:
        result, failed = web_search_failure_result(str(exc))
        _emit_events(state, failed)
        return {"web_result": result, "execution_events": [*started, *failed]}


def _format_rag_context(docs: list[dict[str, Any]]) -> str:
    return "\n\n---\n\n".join(
        f"[{index}] {item.get('filename', 'Unknown')} (Page {item.get('page_number', 'N/A')}):\n{item.get('text', '')}"
        for index, item in enumerate(docs, 1)
    )


def _format_web_context(sources: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[W{index}] {item['title']} ({item['domain']})\n{item.get('snippet', '')}\n{item['url']}"
        for index, item in enumerate(sources, 1)
    )


def answer_synthesis_node(state: SupervisorState) -> dict[str, Any]:
    if state.get("answer"):
        return {}
    rag_result = state.get("rag_result") or {}
    rag_trace = rag_result.get("rag_trace") or {}
    if rag_trace.get("retrieval_status") in {
        "needs_clarification",
        "needs_scope_selection",
    }:
        return {"rag_trace": rag_trace, "answer": ""}
    docs = rag_result.get("docs") or []
    web_result = state.get("web_result") or {}
    web_sources = web_result.get("sources") or []
    if not docs and not web_sources:
        if state["route_decision"].route == "knowledge_base":
            return {"answer": "知识库中没有找到可靠的相关信息，暂时无法基于知识库回答这个问题。"}
        return {"answer": "暂时没有获得足以可靠回答的外部证据。"}

    evidence_sections = []
    citation_rules = []
    if docs:
        evidence_sections.append(f"知识库片段：\n{_format_rag_context(docs)}")
        citation_rules.append("知识库事实用 [1]、[2] 标注")
    if web_sources:
        evidence_sections.append(f"网页来源：\n{_format_web_context(web_sources)}")
        citation_rules.append("网页事实用 [W1]、[W2] 标注")

    from backend.chat.runtime import model
    answer = model.invoke([
        SystemMessage(content=(
            "请仅基于给出的证据回答问题。"
            f"{'；'.join(citation_rules)}。资料不足时明确说明。"
            "不要披露内部检索过程或隐藏推理。"
        )),
        HumanMessage(content=f"问题：{state['question']}\n\n" + "\n\n".join(evidence_sections)),
    ]).content
    return {"answer": str(answer or ""), "rag_trace": rag_trace}


def build_execution_trace_node(state: SupervisorState) -> dict[str, Any]:
    decision = state["route_decision"]
    rag_trace = dict(state.get("rag_trace") or (state.get("rag_result") or {}).get("rag_trace") or {})
    rag_trace.update({
        "supervisor_route": decision.route,
        "supervisor_reason": decision.reason,
    })
    web_result = state.get("web_result")
    if web_result:
        rag_trace.update({
            "web_search_status": web_result.get("status", "not_requested"),
            "web_sources": web_result.get("sources", []),
        })
        if web_result.get("error"):
            rag_trace["web_search_error"] = web_result["error"]
    return {"rag_trace": rag_trace}


def build_supervisor_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node("load_agent_profile", load_profile_node)
    graph.add_node("route_request", route_request_node)
    graph.add_node("parallel_tools", lambda _state: {})
    graph.add_node("direct_answer", direct_answer_node)
    graph.add_node("knowledge_base_tool", knowledge_base_tool_node)
    graph.add_node("web_search_tool", web_search_tool_node)
    graph.add_node("answer_synthesis", answer_synthesis_node)
    graph.add_node("build_execution_trace", build_execution_trace_node)
    graph.add_edge(START, "load_agent_profile")
    graph.add_edge("load_agent_profile", "route_request")
    graph.add_conditional_edges("route_request", route_after_decision)
    graph.add_conditional_edges("parallel_tools", parallel_tool_sends)
    graph.add_edge("direct_answer", "answer_synthesis")
    graph.add_edge("knowledge_base_tool", "answer_synthesis")
    graph.add_edge("web_search_tool", "answer_synthesis")
    graph.add_edge("answer_synthesis", "build_execution_trace")
    graph.add_edge("build_execution_trace", END)
    return graph.compile()


def run_supervisor(
    question: str,
    conversation: list[Any],
    request_context: Any,
) -> dict[str, Any]:
    """Run one request through the outer LangGraph supervisor."""
    result = build_supervisor_graph().invoke({
        "question": question,
        "conversation": conversation,
        "request_context": request_context,
        "execution_events": [],
    })
    return {
        "answer": str(result.get("answer") or ""),
        "rag_trace": result.get("rag_trace") or {},
        "rag_result": result.get("rag_result") or {},
    }
