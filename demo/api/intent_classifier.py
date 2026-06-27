# demo/api/intent_classifier.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from models import ClassifiedIntent, PipelineState

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Je classificeert klantvragen voor een Nederlands bedrijf.
Categorieën:
- info: vragen over producten, diensten, openingstijden, beleid, garantie
- klacht: problemen met bestelling, levering, kwaliteit of dienst
- commercieel: vragen over prijzen, offertes, uitbreidingen, abonnementen
- onbekend: alles wat niet in bovenstaande past

Geef een confidence score (0.0–1.0) en korte reasoning in het Nederlands."""),
    ("human", "Klantvraag: {message}"),
])


def _make_chain():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return _PROMPT | llm.with_structured_output(ClassifiedIntent)


def classify_intent(state: PipelineState) -> dict:
    chain = _make_chain()
    result = chain.invoke({"message": state["customer_message"]})
    return {"intent": result}
