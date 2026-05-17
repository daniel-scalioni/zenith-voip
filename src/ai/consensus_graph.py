from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from typing import TypedDict, Annotated, Any
from src.extraction.regex_layer import RegexExtractor
from src.extraction.llm_layer import LocalLLMExtractor
from src.events.redis_streams import event_bus
from src.config import settings


class AgentState(TypedDict):
    call_id: str
    transcript: str
    entities: dict[str, list[dict]]
    sentiment: str
    sentiment_score: float
    proposed_action: str
    justification: str
    revision_notes: str
    final_decision: str
    human_bypass: bool
    iteration: int


class ConsensusGraph:
    def __init__(self):
        self.extractor = RegexExtractor()
        self.llm = LocalLLMExtractor()
        self.redis_saver = RedisSaver.from_conn_info(host="redis", port=6379)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)

        builder.add_node("extractor", self._extractor_node)
        builder.add_node("reviewer", self._reviewer_node)
        builder.add_node("decider", self._decider_node)

        builder.set_entry_point("extractor")
        builder.add_edge("extractor", "reviewer")
        builder.add_edge("reviewer", "decider")
        builder.add_conditional_edges(
            "decider",
            self._decide_loop_or_end,
            {"reviewer": "reviewer", END: END},
        )

        return builder.compile(checkpointer=self.redis_saver)

    async def _extractor_node(self, state: AgentState) -> dict:
        entities = await self.extractor.extract(state["transcript"])
        return {"entities": entities, "iteration": state.get("iteration", 0) + 1}

    async def _reviewer_node(self, state: AgentState) -> dict:
        review_note = ""
        if state["entities"]:
            for entity_type, matches in state["entities"].items():
                for m in matches:
                    if m.get("sensitive", False):
                        sanitized = await self.llm.sanitize(m["value"], entity_type, state["transcript"])
                        review_note += f"Sanitized {entity_type}: {sanitized}\n"
        return {"revision_notes": review_note}

    async def _decider_node(self, state: AgentState) -> dict:
        has_entities = bool(state.get("entities"))
        decision = "approved" if has_entities and state.get("sentiment_score", 0) >= -0.3 else "rejected"
        if state.get("human_bypass", False):
            decision = "bypass"
        return {"final_decision": decision}

    def _decide_loop_or_end(self, state: AgentState) -> str:
        if state["final_decision"] == "rejected" and state["iteration"] < 3:
            return "reviewer"
        return END

    async def run(self, call_id: str, transcript: str, sentiment: str = "neutral", sentiment_score: float = 0.0) -> dict:
        initial_state = AgentState(
            call_id=call_id,
            transcript=transcript,
            entities={},
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            proposed_action="",
            justification="",
            revision_notes="",
            final_decision="pending",
            human_bypass=False,
            iteration=0,
        )
        config = {"configurable": {"thread_id": call_id}}
        result = await self.graph.ainvoke(initial_state, config)

        await event_bus.publish(settings.REDIS_STREAM_CALL_EVENTS, {
            "call_id": call_id,
            "event": "consensus_complete",
            "decision": result.get("final_decision", "unknown"),
            "entities": str(result.get("entities", {})),
        })

        return result


consensus_graph = ConsensusGraph()
