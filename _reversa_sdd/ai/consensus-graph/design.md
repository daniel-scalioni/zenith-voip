# Consenso, Design

**Interface:** `run(call_id, transcript, sentiment, sentiment_score) → dict {final_decision}`
**Estado:** AgentState {call_id, transcript, entities, sentiment, sentiment_score, final_decision, iteration}
**Fluxo:** extractor → reviewer → decider → (approved → END | rejected + iteration < 3 → extractor | rejected + iteration >= 3 → END)
**Origem:** `src/ai/consensus_graph.py:40-72` 🟢
