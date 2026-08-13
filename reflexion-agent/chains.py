from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
load_dotenv()
reflexion_prompt = ChatPromptTemplate.from_messages(
    [
        (
        "system", "You are viral tweeter influencer grading a tweet. Generate critique and recommendations for the user"
        "Always provide detailed recommendations for the user to improve their tweet. Be specific and provide examples."
        ),
        MessagesPlaceholder(variable_name="messages")
    ]
)

generation_prompt = ChatPromptTemplate.from_messages(
    [
        ( "system", "You are a techie tweeter influencer tasked with writing tweeter posts"
        "Generate best twitter posts possible for the user request"
        "If a user provides critique and recommendations, use them to improve the tweet."
        ),
        MessagesPlaceholder(variable_name="messages")
    ]
)

llm = ChatOpenAI()
generation_chain = generation_prompt | llm
reflection_chain = reflexion_prompt | llm

