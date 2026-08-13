
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.graph.message import add_messages
from chains import generation_chain, reflection_chain
load_dotenv()

class MessageGraph(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

REFLECT = "reflect"
GENERATE = "generate"

def generation_mode(state: MessageGraph):
        return {"messages": [generation_chain.invoke({"messages": state["messages"]})]}
    
def reflection_mode(state: MessageGraph):
        res =  reflection_chain.invoke({"messages": state["messages"]})
        return {"messages": [HumanMessage(content=res.content)]}
    
    #builder = StateGraph(state_schema=MessageGraph)
builder = StateGraph(state_schema=MessageGraph)
builder.add_node(GENERATE, generation_mode)
builder.add_node(REFLECT, reflection_mode)
builder.set_entry_point(GENERATE)

def should_continue(state: MessageGraph):
        if len(state["messages"]) > 6:
          return END
        return REFLECT

builder.add_conditional_edges(GENERATE, should_continue, path_map={END: END, REFLECT: REFLECT})
builder.add_edge(REFLECT, GENERATE)
graph = builder.compile()
print(graph.get_graph().draw_mermaid())



def main():
    print("Hello from reflexion-agent!")

if __name__ == "__main__":
    main()
input = HumanMessage(content="Make this tweet better: 'I love programming!'")
response = graph.invoke({"messages": [input]})