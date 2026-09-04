"""
LangGraph StateGraph Workflow Construction for BIS Agent.
"""
from __future__ import annotations

import logging
from typing import Dict, Tuple

from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from langgraph.graph import END, START, StateGraph

from src.agent.nodes import AgentNodes
from src.config import CONFIG
from src.schemas import DOMAIN_COLLECTIONS, AgentState, Intent, TokenTracker
from src.tools.cache import ResponseCache

from src.tools.vector_store import get_vector_store

logger = logging.getLogger("bis_graph")


def initialize_components() -> Tuple[ChatGoogleGenerativeAI, any, any, Dict[str, any]]:
    """Initialize LLM, Embeddings, Catalog Retriever, and Domain Collections."""
    provider = CONFIG.embedding_provider.lower()
    if provider == "fastembed":
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        embeddings = FastEmbedEmbeddings(model_name=CONFIG.embedding_model)
    elif provider == "google":
        embeddings = GoogleGenerativeAIEmbeddings(model=CONFIG.embedding_model)
    elif provider in ("mistral", "mistralaiembeddings"):
        from langchain_mistralai import MistralAIEmbeddings
        embeddings = MistralAIEmbeddings(model=CONFIG.embedding_model)
    else:
        embeddings = OllamaEmbeddings(model=CONFIG.embedding_model, base_url=CONFIG.embedding_base_url)

    llm = ChatGoogleGenerativeAI(model=CONFIG.llm_model, temperature=CONFIG.llm_temperature)

    # Catalog retriever (default collection)
    catalog_vector_store = get_vector_store("catalog_search", embeddings)
    catalog_retriever = catalog_vector_store.as_retriever(search_kwargs={"k": CONFIG.retriever_k})

    # Domain Vector DBs (PGVector on Supabase or local Chroma)
    domain_chromadbs: Dict[str, any] = {}
    for domain in DOMAIN_COLLECTIONS:
        domain_chromadbs[domain.value] = get_vector_store(domain.value, embeddings)

    return llm, embeddings, catalog_retriever, domain_chromadbs


def build_graph(
    token_tracker: TokenTracker = None,
    response_cache: ResponseCache = None,
):
    """Construct and compile the LangGraph workflow."""
    if token_tracker is None:
        token_tracker = TokenTracker()
    if response_cache is None:
        response_cache = ResponseCache()

    llm, embeddings, catalog_retriever, domain_chromadbs = initialize_components()

    nodes = AgentNodes(
        llm=llm,
        embeddings=embeddings,
        catalog_retriever=catalog_retriever,
        domain_chromadbs=domain_chromadbs,
        response_cache=response_cache,
        token_tracker=token_tracker,
    )

    workflow = StateGraph(AgentState)

    workflow.add_node("contextualize_query", nodes.contextualize_query)
    workflow.add_node("intent_classifier", nodes.intent_classifier)
    workflow.add_node("retrieve_catalog", nodes.retrieve_catalog)
    workflow.add_node("synthesize_response", nodes.synthesize_response)

    for domain in DOMAIN_COLLECTIONS:
        workflow.add_node(domain.value, nodes.retrieve_domain(domain))
        workflow.add_edge(domain.value, "synthesize_response")

    workflow.add_edge(START, "contextualize_query")
    workflow.add_edge("contextualize_query", "intent_classifier")

    routes = {domain.value: domain.value for domain in DOMAIN_COLLECTIONS}
    routes[Intent.CATALOG_SEARCH.value] = "retrieve_catalog"
    routes[Intent.CHAT.value] = "synthesize_response"

    workflow.add_conditional_edges("intent_classifier", lambda s: s["intent"], routes)
    workflow.add_edge("retrieve_catalog", "synthesize_response")
    workflow.add_edge("synthesize_response", END)

    return workflow.compile(), nodes
