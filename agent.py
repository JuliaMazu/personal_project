from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode
from langchain.chat_models import init_chat_model
from langgraph.graph import MessagesState, StateGraph
import os
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from langgraph.graph import END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver


#load_dotenv() 

kg = Neo4jGraph(
    url=os.getenv("NEO4J_URI"), 
    username=os.getenv("NEO4J_USERNAME"), 
    password=os.getenv("NEO4J_PASSWORD"), 
    database=os.getenv("NEO4J_DATABASE")
)

@tool(response_format="content_and_artifact")
def neo4j_vector_search(question):
  """Search for similar nodes using the Neo4j vector index"""
  print("using tools")
  vector_search_query = """
    WITH genai.vector.encode(
      $question,
      "OpenAI",
      {
        token: $openAiApiKey,
        endpoint: $openAiEndpoint
      }) AS question_embedding
    CALL db.index.vector.queryNodes($index_name, $top_k, question_embedding) yield node, score
    MATCH (a:Article)-[]-(node) 
    RETURN node.text AS text, a.title AS article_title, a.journal as article_journal
  """
  similar = kg.query(vector_search_query,
                     params={
                      'question': question,
                      "openAiApiKey": os.getenv("OPENAIKEY"),
                      "openAiEndpoint": os.getenv("OPENAIENDPOINT"),
                      'index_name': 'form_10k_chunks',
                      'top_k': 15})
  retrieved_docs = [result["text"] for result in similar]
  serialized = [result["article_journal"]+ "/ "+ result["article_title"].capitalize() for result in similar]
  print("tools was called")
  return   "; ".join(retrieved_docs), " ".join(serialized)



graph_builder = StateGraph(MessagesState)

llm = init_chat_model("gemini-2.5-flash", 
                      model_provider="google_genai", 
                      api_key=os.getenv("GEMINI_KEY"))

# Step 1: Generate an AIMessage that may include a tool-call to be sent.
def query_or_respond(state: MessagesState):
    """Generate tool call for retrieval or respond."""
    print("i am in query or respond node")
    llm_with_tools = llm.bind_tools([neo4j_vector_search])
    TOOL_CALL_SYSTEM_MESSAGE = SystemMessage(
    content=(
        "You are an expert search assistant. Your SOLE purpose is to determine which tool, "
        "if any, should be called to gather context for the user's request. "
        "ALWAYS call the `neo4j_vector_search` tool with the user's full question as the input, "
        "even if you think you have enough information, because your final response "
        "MUST be based on fresh context."
    )
)
    messages_with_instruction = [TOOL_CALL_SYSTEM_MESSAGE] + state["messages"]

    response = llm_with_tools.invoke(messages_with_instruction)
    # MessagesState appends messages to state instead of overwriting
    return {"messages": [response]}


# Step 2: Execute the retrieval.
tools = ToolNode([neo4j_vector_search])


# Step 3: Generate a response using the retrieved content.
import json

def generate(state: MessagesState):
    """Generate answer."""
    # Find the most recent ToolMessage and access its content
    print("try to generate answer")
    recent_tool_messages = []
    for message in reversed(state["messages"]):
        if message.type == "tool":
            recent_tool_messages.append(message)
        else:
            break
    tool_messages = recent_tool_messages[::-1]
   # print(tool_messages)
    # Format into prompt
    docs_content = "\n\n".join(doc.content for doc in tool_messages)
    docs_artifacts = "\n\n".join(doc.artifact for doc in tool_messages)
    print("total symbols nb ", len(docs_content))
   # print(docs_artifacts)
    system_message_content = (
            "You are a scientific research assistant. Summarize the provided context to answer the user's question. "
            "Your response must adhere to the following rules:\n\n"
            "Break down large documents into smaller 15 sections and summarize each section before providing the full response. Do not mention your breakdown result to user "
            "1. You MUST analyze and synthesize ALL provided documents and sources. Do NOT omit any key topic (e.g., muscle adaptation, bone health, skin, intestinal health).\n"
            "2. You must include all scientific details, such as molecules, processes, and specific findings.\n"
            "3. Emphasize and explain conflicting or ambiguous results from the text.\n"
            "4. Do not include any numerical citations, bracketed numbers, or source references in your final answer..\n"
            "5. Your answer MUST be based exclusively on the provided context. If the context is insufficient, you MUST state I dont know.\n"
            "6. Use only tools as an information source.\n"
            "7. Print ALL the sources at the end of your answer, list it with numbers, be sure to print all"
            "8. Use only provided context as a source of data"
            "Review and meta-analysis articles data has more impact than just typical research. "
            "Use of placebo, double-blind stydies, high number of participants increase data reliability. "
            "Your response MUST be structured into clear sections using headings to cover each major topic. "
            "--- CONTEXT ---\n"
            f"{docs_content}\n\n"
            "--- SOURCES ---\n"
            f"{docs_artifacts}\n"
        )

    conversation_messages = [
        message
        for message in state["messages"]
        if message.type in ("human", "system")
        or (message.type == "ai" and not message.tool_calls)
    ]

    prompt = [SystemMessage(system_message_content)] + conversation_messages

    response = llm.invoke(prompt)
    return {"messages": [response]}


graph_builder.add_node(query_or_respond)
graph_builder.add_node(tools)
graph_builder.add_node(generate)

graph_builder.set_entry_point("query_or_respond")
graph_builder.add_conditional_edges(
    "query_or_respond",
    tools_condition,
    {END: END, "tools": "tools"},
)
graph_builder.add_edge("tools", "generate")
graph_builder.add_edge("generate", END)

memory = MemorySaver()

graph = graph_builder.compile(checkpointer=memory)
