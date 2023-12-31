from openai import OpenAI
import os
from dotenv import load_dotenv

from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.schema.document import Document
from langchain_community.chat_models import ChatOpenAI
from langchain.text_splitter import CharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate

import tiktoken

# load env
load_dotenv()


class ChatRover():

    def __init__(self, gitHubScraper):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.api_key)

        self.gitHubScraper = gitHubScraper

        # Constants
        self.model = "gpt-3.5-turbo-1106"
        self.max_model_tokens = 16000
        self.response_token_limit = self.max_model_tokens // 3
        self.readme_top_k = 5
        self.file_top_k = 10
        self.files_to_scrape = 2

        # Create vector stores for RAG
        self.readme_vector = self.create_readme_vector()
        self.file_vector = self.create_file_vector()

        self.repo = self.gitHubScraper.get_repo_name()
        self.conversation_history = []
        self.conversation_tokens = 0
        self.encoding = tiktoken.encoding_for_model(self.model)

    # Returns vector store where each entry is a single file path
    def create_file_vector(self):
        files = self.gitHubScraper.get_file_paths()
        if not files:
            files = "Files not found."

        print("Creating file vector...")
        split_data = [Document(page_content=file) for file in files]

        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_documents(split_data, embedding=embeddings)
        print("File vector complete!")
        return vectorstore

    # Returns vector store where each entry is a chunk of the Readme
    def create_readme_vector(self):
        data = self.gitHubScraper.get_readme()
        if not data:
            data = "Readme not found."

        print("Creating readme vector...")
        text_splitter = CharacterTextSplitter(chunk_size=3000, chunk_overlap=200)
        split_data = [Document(page_content=chunk) for chunk in text_splitter.split_text(data)]

        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_documents(split_data, embedding=embeddings)
        print("Readme vector complete!")
        return vectorstore
    
    # Returns summary of file contents for a given file_path that is relevant 
    # to the user query
    def code_summary(self, file_path, query):
        custom_prompt = """
        Provide a clear and concise summary on the code that you will be given as it relates to a user query. 
        You should reference specific parts of the code. 
        Be technical. Your summary will be used by another LLM to explain specific parts of the code. 
        Focus on those parts that are most relevant to the user query, the user may ask for specific code snippets which you will provide.
        Do not speak to or address the user. 
        Limit your response to 200 words.
        Code: {code}
        User Query: {query}
        """
        prompt = ChatPromptTemplate.from_template(custom_prompt)
        model = ChatOpenAI(openai_api_key=self.api_key, model_name=self.model)
        chain = prompt | model

        code = self.gitHubScraper.get_file_raw(file_path)
        if code:
            code = self.trim(code, self.max_model_tokens)
            input_dict = {'code': code, 'query': query}
            res = chain.invoke(input_dict).content
            return res
        return "Code not found."

    # Returns relevant, trimmed, and prompted input for model via vector similarity search
    def retrieve_context(self, query):
        readme_query = self.readme_vector.similarity_search(query, self.readme_top_k)
        file_query = self.file_vector.similarity_search(query, self.file_top_k)

        readme_string = "\n".join(doc.page_content for doc in readme_query)
        file_string = ",".join(doc.page_content for doc in file_query)

        readme_response = self.trim(readme_string, self.response_token_limit)
        file_response = self.trim(file_string, self.response_token_limit)

        content_response = ""
        i = 0
        while i < len(file_query) and i < self.files_to_scrape:
            file_path = file_query[i].page_content
            summary = self.code_summary(file_path, query)
            content_response += "File: " + file_path + "\n" + "Summary: " + summary + "\n"
            i += 1

        role_prompt = f"""
            As 'RepoRover', you are a specialized AI expert on the '{self.repo}' repository. 
            Your expertise includes detailed knowledge of the repository's structure, 
            critical portions of the README, and summaries of key files based on user queries. 
            You do not have to use the summaries of files if they are not relevant. 
            If they are relevant, feel free to copy them verbatum or you may choose to extract 
            parts of them to best answer the user. 
            Below is the relevant file structure, selected README excerpts, and summaries of important files. 
            Using this information, please provide precise answers to the following question, 
            referencing specific files or sections when useful. 
            You are responding directly to the user. Only address the user in your response.

            README.md portion: '{readme_response}'
            Comma seperated file structure: '{file_response}'
            Summary of file contents: '{content_response}'
            User query: '{query}'
            """
        return role_prompt

    # Trim text by number of tokens to obey context window size
    def trim(self, text, token_limit):
        tokens = self.encoding.encode(text)
        if len(tokens) > token_limit:
            trimmed_tokens = tokens[:token_limit]
            text = self.encoding.decode(trimmed_tokens)
        return text

    def token_count(self, text):
        return len(self.encoding.encode(text))

    # add conversation to history and keep history size below maxtokens
    def update_history(self, role, content):
        self.conversation_history.append({"role": role, "content": content})
        self.conversation_tokens += self.token_count(content)

        while self.conversation_tokens > self.max_model_tokens and self.conversation_history:
            removed_entry = self.conversation_history.pop(0)
            self.conversation_tokens -= self.token_count(removed_entry['content'])

    # Interact with the LLM and update conversation history
    # Yields to take advantage of chat streaming
    def run_chat(self, user_input):
        enhanced_input = self.retrieve_context(user_input)

        self.update_history("user", enhanced_input)
        print("TOKENS: ", self.conversation_tokens)
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=self.conversation_history,
            stream=True
        )

        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response_chunk = chunk.choices[0].delta.content
                yield response_chunk
                response += response_chunk
                
        self.update_history("assistant", response)