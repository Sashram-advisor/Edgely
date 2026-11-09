
import ollama
import numpy as np
from pathlib import Path
import re

# Load the study material
file_path = Path("data/study_material.txt")
study_material = file_path.read_text(encoding="utf-8")

print("Study material loaded successfully!")
print(f"Characters loaded: {len(study_material)}")


# Split the material into individual sections
def split_sections(material):
    sections = re.split(r"\n(?=## )", material)
    return [section.strip() for section in sections if section.strip()]


# Convert text into an embedding using Ollama
def get_embedding(text):
    result = ollama.embeddings(
        model="nomic-embed-text",
        prompt=text
    )
    return np.array(result["embedding"], dtype=float)


# Create embeddings for the study material
print("\nPreparing study material for semantic search...")

sections = split_sections(study_material)
section_embeddings = []

for section in sections:
    section_embeddings.append(get_embedding(section))

print(f"Prepared {len(sections)} sections successfully!")


# Find the most relevant sections for a question
def retrieve_relevant_sections(question, max_sections=2):
    question_embedding = get_embedding(question)
    scored_sections = []

    for section, section_embedding in zip(sections, section_embeddings):
        denominator = (
            np.linalg.norm(question_embedding)
            * np.linalg.norm(section_embedding)
        )

        if denominator == 0:
            similarity = 0
        else:
            similarity = (
                np.dot(question_embedding, section_embedding)
                / denominator
            )

        scored_sections.append((similarity, section))

    scored_sections.sort(key=lambda item: item[0], reverse=True)

    selected = scored_sections[:max_sections]

    return "\n\n".join(section for score, section in selected)


# Start the chatbot
print("\n=== AWS AI Tutor ===")
print("Ask questions about AWS. Type 'exit' to quit.\n")

while True:
    question = input("You: ").strip()

    if question.lower() == "exit":
        print("Goodbye!")
        break

    if not question:
        continue

    try:
        relevant_material = retrieve_relevant_sections(question)

        response = ollama.chat(
            model="llama3.2:3b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AWS Certified Cloud Practitioner tutor. "
                        "Answer using only the relevant study material below. "
                        "If the material does not contain enough information "
                        "to answer, say that the topic is not covered in the "
                        "provided material. Do not invent facts or claim "
                        "unsupported information came from the material. "
                        "Explain concepts clearly and use examples from "
                        "the material when helpful.\n\n"
                        "RELEVANT STUDY MATERIAL:\n"
                        + relevant_material
                    ),
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
        )

        print("\nAI Tutor:", response["message"]["content"], "\n")

    except Exception as error:
        print("\nSomething went wrong:", error, "\n")
