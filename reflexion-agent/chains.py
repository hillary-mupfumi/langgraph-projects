from dotenv import load_dotenv
import datetime
from langchain_core.output_parsers import JsonOutputToolsParser, PydanticToolsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from schemas import AnswerQuestion, ReviseAnswer

load_dotenv()

actor_chat_prompt_template = ChatPromptTemplate.from_messages(
    [
    (
        "system",
        """ You are an expert research.
        current time: {time}
        1. {first_instruction}
        2. Reflect and critique  your answer. Be severe to maximise improvement
        3. Recommend search queries to research infomartion and improve your answer
     """
            ),
            MessagesPlaceholder(variable_name="messages"),
            ("system","Answer the user question above using the above format")
    ]
).partial(
    time=lambda: datetime.datetime.now().isoformat(),
)

llm = ChatOpenAI(model="gpt-4o-mini")
parser = JsonOutputToolsParser(return_id=True)
parser_pydentic = PydanticToolsParser(tools=[AnswerQuestion])

first_responder_prompt_template = actor_chat_prompt_template.partial(first_instruction="Provide a detailed 250 word answer.")

first_responder = first_responder_prompt_template | llm.bind_tools(tools=[AnswerQuestion], tool_choice="AnswerQuestion")

revise_instructions = """Revise your previous answer using the new information.
        - You should use the previous critique to add important information to your answer.
        - You MUST include numerical citations in your revised answer to ensure it can be verified.
        - Add a "References" section to the bottom of your answer (which does not count towards the word limit). In form of:
            - [1] https://example.com
            - [2] https://example.com
    - You should use the previous critique to remove superfluous information from your answer and make SURE it is not more than 250 words.
"""

revisor = actor_chat_prompt_template.partial(
    first_instruction=revise_instructions
) | llm.bind_tools(tools=[ReviseAnswer], tool_choice="ReviseAnswer")

if __name__ == "__main__":
    human_message = HumanMessage(content="Write about AI powered Soc problem domain. List startups that do that and raised capital")


    chain = (
        first_responder_prompt_template 
        | llm.bind_tools(tools=[AnswerQuestion], tool_choice="AnswerQuestion")
        | parser_pydentic
    )

    res =  chain.invoke(input={"messages":[human_message]})
    print(res)