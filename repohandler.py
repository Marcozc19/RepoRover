import chromadb
from chromadb.utils import embedding_functions


class GitHubRepoHandler:
    def __init__(self):
        # Initialize ChromaDB Client
        # self.chroma_client = chromadb.Client()
        self.chroma_client = chromadb.PersistentClient(path="chroma_data")
        # self.chroma_client.reset()
        self.emb = embedding_functions.DefaultEmbeddingFunction()
        # Check and create collections for README and file structure if they don't exist

        self.readme_collection = self.chroma_client.get_or_create_collection(name="readme", embedding_function=self.emb)
        self.file_structure_collection = self.chroma_client.get_or_create_collection(name="file_structures", embedding_function=self.emb)


        # metas = []
        # for chunk in range(0, len(file_paths), chunks):
        #     meta = ""
        #     end = min(chunk+chunks, len(file_paths) - 1)
        #     for path in file_paths[chunk:end]:
        #         meta += f"{path}\n"
        #     meta.append(metas)

    # def update_file_structure(self, file_paths):
    #     """
    #     Update ChromaDB with the file structure from a GitHub repository.
    #     Each file path is stored as a separate document with a sequential ID.
    #     """

    #     self.chroma_client.delete_collection(name="file_structures")
    #     self.file_structure_collection = self.chroma_client.create_collection(name="file_structures", embedding_function=self.emb)
        
    #     for index, path in enumerate(file_paths):
    #         self.file_structure_collection.add(
    #             documents=[path],
    #             ids=[f"files_{index}"]  # Assigning a sequential ID
    #         )
    #     print("File structure updated in ChromaDB.")

    # def update_file_structure(self, file_paths, batch_size=25):
    #     """
    #     Update ChromaDB with the file structure from a GitHub repository using batching.
    #     Each document in a batch contains multiple file paths in its metadata as a string.
    #     """
    #     print("start update file struct")
    #     # Deleting the existing collection
    #     self.chroma_client.delete_collection(name="file_structures")
    #     self.file_structure_collection = self.chroma_client.create_collection(name="file_structures", embedding_function=self.emb)

    #     documents = []
    #     metadatas = []
    #     ids = []
    #     batch_count = 0

    #     for index, path in enumerate(file_paths):
    #         # Check if it's time to start a new batch
    #         if index % batch_size == 0 and index > 0:
    #             # Add the current batch to the collection
    #             self.file_structure_collection.add(documents=documents, metadatas=metadatas, ids=ids)

    #             # Reset for the next batch
    #             documents = []
    #             metadatas = []
    #             ids = []
    #             batch_count += 1

    #         # Initialize a new batch
    #         if index % batch_size == 0:
    #             documents.append(f"Batch_{batch_count + 1}")
    #             metadatas.append({"file_paths": ""})
    #             ids.append(f"batch_{batch_count}")

    #         # Append the current path to the metadata string, separated by a newline or another delimiter of your choice
    #         metadatas[-1]["file_paths"] += path + "\n"

    #     # Add the final batch if it's not empty
    #     if documents:
    #         self.file_structure_collection.add(documents=documents, metadatas=metadatas, ids=ids)

    #     print("File structure updated in ChromaDB with batching.")

    import itertools

    def update_file_structure(self, file_paths, batch_size=75, metadata_batch_size=15):
        """
        Update ChromaDB with the file structure from a GitHub repository using batching.
        Batches of 50-100 documents are added, with each document's metadata containing 5-10 file paths.
        """
        print("Start update file structure")

        # Deleting the existing collection
        self.chroma_client.delete_collection(name="file_structures")
        self.file_structure_collection = self.chroma_client.create_collection(name="file_structures", embedding_function=self.emb)

        for batch_start in range(0, len(file_paths), batch_size):
            # Creating a batch of documents
            batch_end = min(batch_start + batch_size, len(file_paths))
            batch_file_paths = file_paths[batch_start:batch_end]

            documents = []
            metadatas = []
            ids = []

            # Grouping file paths into metadata batches
            for meta_index, meta_start in enumerate(range(0, len(batch_file_paths), metadata_batch_size)):
                meta_end = min(meta_start + metadata_batch_size, len(batch_file_paths))
                metadata_file_paths = batch_file_paths[meta_start:meta_end]

                # Create a document for each metadata batch
                documents.append(f"Batch_{batch_start // batch_size + 1}_Doc_{meta_index + 1}")
                metadatas.append({"file_paths": "\n".join(metadata_file_paths)})
                ids.append(f"batch_{batch_start // batch_size}_doc_{meta_index}")

            # Add the batch of documents to the collection
            self.file_structure_collection.add(documents=documents, metadatas=metadatas, ids=ids)

        print("File structure updated in ChromaDB with batching.")


    def query_file_structure(self, query_text, n_results=5):
        """
        Query the file structure collection based on a text query.
        """
        context = self.file_structure_collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return context

    def update_readme(self, readme_content):
        """
        Update ChromaDB with the README content. 
        Since there's only ever one README, it replaces any existing data.
        """

        self.chroma_client.delete_collection(name="readme")
        self.file_structure_collection = self.chroma_client.create_collection(name="readme", embedding_function=self.emb)

        self.readme_collection.add(
            documents=[readme_content],
            ids=["single_readme"]  # A constant ID since there's only one README
        )
        print("README updated in ChromaDB.")

    def query_readme(self, query_text):
        """
        Query the README collection based on a text query.
        """
        context = self.readme_collection.query(
            query_texts=[query_text],
            filter={"id": "single_readme"},
            n_results=1
        )
        return context




# # Example usage
# repo_handler = GitHubRepoHandler()

# # Simulate fetching data from a GitHub repository
# readme_content = "Content of README"  # Replace with actual README content
# file_paths = ["/src/main.py", "/README.md", "/docs/guide.md"]  # Example file paths

# # Update ChromaDB with the GitHub data
# repo_handler.update_readme(readme_content)
# repo_handler.update_file_structure(file_paths)

# # Example queries
# readme_query_result = repo_handler.query_readme("how do I install the app? (readme Q)")
# file_structure_query_result = repo_handler.query_file_structure("where is the app file located? (file struct Q)")

# # Process the query results as needed

