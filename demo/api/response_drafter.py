# demo/api/response_drafter.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from models import DraftedResponse, PipelineState

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Je bent een klantenservice medewerker van een Nederlands bedrijf.
Schrijf een professioneel, vriendelijk antwoord op de klantvraag.
Gebruik ALLEEN informatie uit de aangeboden kennisbank passages.
Schrijf in het Nederlands, formele toon (u/uw).
Begin met "Geachte klant," en sluit af met "Met vriendelijke groet, GroenTech Services".
Als de kennisbank geen relevant antwoord bevat, vermeld dit eerlijk."""),
    ("human", "Klantvraag: {message}\n\nKennisbank:\n{context}\n\nAntwoord:"),
])


def _make_chain():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return _PROMPT | llm.with_structured_output(DraftedResponse)


def draft_response(state: PipelineState) -> dict:
    chain = _make_chain()
    knowledge = state.get("knowledge")
    context = (
        "\n\n---\n\n".join(knowledge.passages)
        if knowledge and knowledge.passages
        else "Geen relevante informatie gevonden."
    )
    result = chain.invoke({"message": state["customer_message"], "context": context})
    return {"draft": result, "retry_count": state.get("retry_count", 0)}
