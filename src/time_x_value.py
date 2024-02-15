from dotenv import load_dotenv, find_dotenv
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from datetime import datetime
from modules.set_model import llm_model
from langchain.callbacks import get_openai_callback
from modules.evaluation import generate_qas, evaluate
from modules.results_data import ResultsData
from modules.markdown_file_gen import results_data_to_markdown_table, write_markdown_table_to_file
from modules.vector_db import vct_db_filename_gen, check_and_load_vector_db

def qa_analysis(llm, chain_type, retriever, verbose, query, number, results_data):
    """
    Initializes a QA analysis with a given language model, chain type, and retriever.
    Then, it runs the QA analysis, timing its execution and printing the response along with the execution time.
    """
    # Initialize the RetrievalQA object with the specified parameters.
    qa = RetrievalQA.from_chain_type(
        llm=llm, 
        chain_type=chain_type, 
        retriever=retriever, 
        verbose=verbose
    )

    # Measure number of tokens used
    with get_openai_callback() as cb:
        start = datetime.now()

        try:
            # Execute the QA analysis
            response = qa.invoke(query)
        except ValueError as e: 
            response = e

        end = datetime.now()
    
    tokens_used = cb.total_tokens

    # Calculate the difference between the end and start timestamps to get the execution duration.
    # The duration is converted to milliseconds for a more precise and readable format.
    td = (end - start).total_seconds() * 10**3
    
    print(f"Response: {response}\nThe time of execution of above program is : {td:.03f}ms")

    found = False
    for item in results_data:
        if item.chain_type == chain_type:
            # Update the existing dictionary
            item.append_evaluation(time=td, tokens_used=tokens_used, example_number=number, 
                         predicted_query=query, answer=response)
            found = True
            break

    if not found:
        # Append a new instance of ResultsData if no matching chain_type was found
        results_data.append(ResultsData(chain_type=chain_type, time=td, tokens_used=tokens_used, 
                                        example_number=number, predicted_query=query, answer=response))

    print("\n\nTESTING\n:" + '\n'.join([str(item) for item in results_data]))

    return results_data


def main():
    # Basic Setup
    _ = load_dotenv(find_dotenv()) # read local .env file
    results_data = []
    strategies = ["stuff", "map_reduce", "refine", "map_rerank"]

    # Load data into vector db or use existing one
    file_path = '../data/OutdoorClothingCatalog_1000.csv'
    embedding = OpenAIEmbeddings()  # Define embedding

    # Check if vector DB exists for the CSV, and load or create accordingly
    db = check_and_load_vector_db(file_path, embedding)

    queries = ["Please suggest a shirt with sunblocking", "Please suggest a shirt with sunblocking and tell me why this one", "Please suggest three shirts with sunblocking and tell me why. Give this back to me in markdown code as a table", "Please suggest three shirts with sunblocking and tell me why. Give this back to me in markdown code as a table, with a summary below outlining why sunblocking is important"]

    # Configure LLM for querying
    # layers vector db on llm to inform decisions and responses
    llm = ChatOpenAI(temperature = 0.0, model=llm_model())
    retriever = db.as_retriever()

    # Manual analysis
    for index, query in enumerate(queries, start=1):
        results_data = qa_analysis(llm, "stuff", retriever, True, query, index, results_data)
        results_data = qa_analysis(llm, "map_reduce", retriever, True, query, index, results_data)
        results_data = qa_analysis(llm, "refine", retriever, True, query, index, results_data)
        results_data = qa_analysis(llm, "map_rerank", retriever, True, query, index, results_data)

    # EXPERIMENTAL LLM QA GEN AND EVALUATION
    for strat in strategies:
        # Generate evaluation Q&As
        tuple = generate_qas(file_path, db, llm, strat) #TODO: change this?
        qa = tuple[0]
        examples = tuple[1]

        # Evaluate 
        results_data = evaluate(strat, qa, examples, llm, results_data)

    # Generate results in markdown
    md_table = results_data_to_markdown_table(results_data)

    # Write results to file
    write_markdown_table_to_file(md_table, "results.md")

if __name__ == '__main__':
    main()