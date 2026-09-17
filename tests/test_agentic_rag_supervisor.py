import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from backend.chat.supervisor import (
    RouteDecision,
    build_execution_trace_node,
    load_agent_profile,
    normalize_tavily_results,
    parallel_tool_sends,
    route_after_decision,
    run_supervisor,
    web_search_failure_result,
)
from backend.schemas.chat import normalize_rag_trace


class SupervisorProfileTests(unittest.TestCase):
    def test_agent_profile_is_loaded_from_project_root_for_each_call(self):
        profile = load_agent_profile()

        self.assertIn("通用", profile)
        self.assertNotIn("水稻", profile)
        self.assertIn("Tavily", profile)


class SupervisorContractTests(unittest.TestCase):
    def test_route_decision_accepts_only_the_four_supervisor_routes(self):
        decision = RouteDecision.model_validate({
            "route": "knowledge_base_and_web_search",
            "reason": "需要知识库证据和当前公开信息",
        })

        self.assertEqual("knowledge_base_and_web_search", decision.route)
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate({"route": "anything", "reason": "x"})

    def test_trace_normalizes_web_sources_and_removes_unknown_fields(self):
        trace = normalize_rag_trace({
            "supervisor_route": "web_search",
            "web_sources": [{
                "title": "稻米资讯",
                "url": "https://example.com/a",
                "domain": "example.com",
                "snippet": "摘要",
                "ignored": 1,
            }],
            "ignored": True,
        })

        self.assertEqual("web_search", trace["supervisor_route"])
        self.assertEqual(["稻米资讯"], [item["title"] for item in trace["web_sources"]])
        self.assertNotIn("ignored", trace)

    def test_trace_drops_web_sources_with_non_http_urls(self):
        trace = normalize_rag_trace({
            "supervisor_route": "web_search",
            "web_sources": [{
                "title": "Unsafe",
                "url": "javascript:alert(1)",
                "domain": "example.com",
            }],
        })

        self.assertEqual([], trace["web_sources"])


class SupervisorRoutingTests(unittest.TestCase):
    def test_router_selects_each_of_the_four_conditional_edges(self):
        expected_nodes = {
            "direct": "direct_answer",
            "knowledge_base": "knowledge_base_tool",
            "web_search": "web_search_tool",
            "knowledge_base_and_web_search": "parallel_tools",
        }

        for route, expected_node in expected_nodes.items():
            with self.subTest(route=route):
                self.assertEqual(
                    expected_node,
                    route_after_decision({
                        "route_decision": RouteDecision(route=route, reason="测试路由"),
                    }),
                )

    def test_parallel_route_emits_one_send_per_tool(self):
        sends = parallel_tool_sends({
            "question": "当前水稻价格",
            "route_decision": RouteDecision(
                route="knowledge_base_and_web_search",
                reason="需要知识库证据和当前公开信息",
            ),
        })

        self.assertEqual(
            {"knowledge_base_tool", "web_search_tool"},
            {send.node for send in sends},
        )


class TavilyTests(unittest.TestCase):
    def test_tavily_result_is_normalized_to_display_safe_web_sources(self):
        sources = normalize_tavily_results({"results": [{
            "title": "Rice bulletin",
            "url": "https://news.example.org/rice",
            "content": "New guidance",
            "score": 0.8,
        }]})

        self.assertEqual("Rice bulletin", sources[0]["title"])
        self.assertEqual("news.example.org", sources[0]["domain"])
        self.assertEqual("New guidance", sources[0]["snippet"])

    def test_web_failure_keeps_other_evidence_available_for_synthesis(self):
        result, events = web_search_failure_result("service unavailable")

        self.assertEqual("failed", result["status"])
        self.assertEqual([], result["sources"])
        self.assertIn("网页搜索暂时不可用", events[0]["label"])


class SupervisorTraceTests(unittest.TestCase):
    def test_combined_route_trace_contains_rag_and_web_source_sections(self):
        trace = build_execution_trace_node({
            "route_decision": RouteDecision(
                route="knowledge_base_and_web_search",
                reason="需要知识库证据和当前公开信息",
            ),
            "rag_result": {
                "rag_trace": {
                    "retrieved_chunks": [{"filename": "rice.pdf"}],
                },
            },
            "web_result": {
                "status": "completed",
                "sources": [{
                    "title": "News",
                    "url": "https://example.com",
                    "domain": "example.com",
                }],
            },
        })["rag_trace"]

        self.assertEqual("knowledge_base_and_web_search", trace["supervisor_route"])
        self.assertEqual("rice.pdf", trace["retrieved_chunks"][0]["filename"])
        self.assertEqual("News", trace["web_sources"][0]["title"])

    @patch("backend.chat.supervisor.build_supervisor_graph")
    def test_run_supervisor_returns_the_graph_answer_and_trace(self, build_graph):
        graph = Mock()
        graph.invoke.return_value = {
            "answer": "当前公开信息显示……[W1]",
            "rag_trace": {
                "supervisor_route": "web_search",
                "web_sources": [],
            },
        }
        build_graph.return_value = graph

        result = run_supervisor("最新水稻政策", [], Mock())

        self.assertEqual("当前公开信息显示……[W1]", result["answer"])
        self.assertEqual("web_search", result["rag_trace"]["supervisor_route"])
        self.assertEqual("最新水稻政策", graph.invoke.call_args.args[0]["question"])


if __name__ == "__main__":
    unittest.main()
