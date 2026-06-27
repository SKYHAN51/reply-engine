# demo/api/quality_checker.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from models import QualityCheckResult, PipelineState

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Je controleert de kwaliteit van klantenservice antwoorden.
Controleer:
1. Bevat het antwoord ALLEEN info uit de kennisbank? (geen hallucination)
2. Is het antwoord professioneel en in het Nederlands?
3. Beantwoordt het de klantvraag daadwerkelijk?

passed=True als alles klopt. hallucination_detected=True als er info wordt geclaimd die niet in de kennisbank staat.
confidence_score: 0.0–1.0 voor algehele kwaliteit."""),
    ("human", "Klantvraag: {message}\n\nKennisbank:\n{context}\n\nAntwoord:\n{response}\n\nBeoordeling:"),
])


def _make_chain():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return _PROMPT | llm.with_structured_output(QualityCheckResult)


def check_quality(state: PipelineState) -> dict:
    chain = _make_chain()
    knowledge = state.get("knowledge")
    context = (
        "\n\n---\n\n".join(knowledge.passages)
        if knowledge and knowledge.passages
        else ""
    )
    draft = state.get("draft")
    result = chain.invoke({
        "message": state["customer_message"],
        "context": context,
        "response": draft.response if draft else "",
    })
    retry_count = state.get("retry_count", 0)
    if not result.passed:
        retry_count += 1
    return {"quality": result, "retry_count": retry_count}
