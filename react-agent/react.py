from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

load_dotenv()

@tool
def trippe(num: float) -> float:
    """
    Param number: The input number to triple.
    Returns: The tripled value of the input number.
    """
    return num * 3

tools = [TavilySearch(max_results=1), trippe]
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools)




