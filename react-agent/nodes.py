from dotenv import load_dotenv
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode
from react import tools, llm

load_dotenv()

SYSTEM_MESSAGE = """
You are a helpful assistant that can use tools to answer questions.
"""

def run_agent_reasoning(state: MessagesState) -> MessagesState:
    """
    This function runs the agent reasoning process using the provided state.
    It utilizes the llm and tools defined in react.py to process the input and generate a response.
    
    Args:
        state (MessageState): The current state of the message, including user input and context.
    
    Returns:
        MessageState: The updated state after processing the input and generating a response.
    """
    response =  llm.invoke([{"role": "system", "content": SYSTEM_MESSAGE}, *state["messages"]])
    return {"messages": [response]}

tool_node = ToolNode(tools)
