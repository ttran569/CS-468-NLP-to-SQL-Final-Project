# Natural Language to SQL using Gemma 3 (LoRA Fine-Tuning)

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Transformers](https://img.shields.io/badge/🤗%20Transformers-4.56.2-yellow)
![LoRA](https://img.shields.io/badge/PEFT-LoRA-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## Overview
This project builds an end-to-end pipeline that converts **natural language queries into SQL** using a fine-tuned **Gemma 3 1B instruction-tuned model**. By applying **LoRA (Low-Rank Adaptation)** on the `sql-create-context` dataset, we significantly improve SQL generation accuracy on a realistic library database.

## Demo
**Input:**
> Find all books written by J.R.R. Tolkien that have reviews

**Output SQL:**
```sql
SELECT b.title
FROM books b
JOIN reviews r ON b.id = r.book_id
WHERE b.author = 'J.R.R. Tolkien';
```

## Features
- Natural Language → SQL query generation
- Fine-tuned Gemma 3 model (LoRA)
- Execution-based evaluation using SQLite
- Supports JOINs, filtering, aggregations
- Lightweight (1B parameter model)

## Dataset
- Source: `b-mc2/sql-create-context` (Hugging Face)
- 7,000 training samples
- 300 evaluation samples
- Token limit: 512

## Database Schema
Custom **library database**:
- `books` (70 records)
- `users` (60 records)
- `reviews` (62 records)
- `checkout` (60 records)

## Model & Training
- Base Model: `unsloth/gemma-3-1b-it`
- Fine-tuning: LoRA (4-bit quantization via Unsloth)
- Hardware: NVIDIA T4 (16GB VRAM)
- Frameworks: Transformers, PEFT, TRL, Datasets

## Installation
```bash
git clone https://github.com/ttran569/CS-468-NLP-to-SQL-Final-Project.git
cd CS-468-NLP-to-SQL-Final-Project

pip install -r requirements.txt
```

## Usage
```python
from transformers import AutoTokenizer, AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained("rahul042/gemma_3_better")
tokenizer = AutoTokenizer.from_pretrained("rahul042/gemma_3_better")

prompt = """
Generate one SQL query using the schema below.

Schema:
[...]

Question: Find all books published after 2000
"""

inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=128)
print(tokenizer.decode(outputs[0]))
```

## Evaluation Metrics
- **Exact Match** – String equality
- **Execution Accuracy** – Correct query results
- **Syntax Error Rate** – Invalid SQL
- **Wrong Result Rate** – Incorrect outputs

## Results
| Metric | Base Model | Fine-tuned Model |
|------|--------|----------------|
| Exact Match | 4.0% | 69.7% |
| Execution Accuracy | 71.7% | **94.0%** |
| Syntax Error Rate | 15.0% | **2.7%** |
| Wrong Result Rate | 13.3% | **3.3%** |

## Key Takeaways
- +22.3% execution accuracy improvement
- 82% reduction in syntax errors
- Reliable SQL generation for real-world queries
- Efficient small-model fine-tuning

## Project Structure
```
├── data/
├── model/
├── evaluation/
├── database/
├── notebooks/
└── README.md
```

## Future Work
- Expand dataset (20k+ samples)
- Schema linking improvements
- Multi-turn query support
- Faster batched inference

## Links
- 🤗 Model: https://huggingface.co/rahul042/gemma_3_better
- 📂 GitHub: https://github.com/ttran569/CS-468-NLP-to-SQL-Final-Project

## Authors
- Rahul S.
- Jonathan C.
- Kunhao L.
- Thomas T.

---
⭐ If you find this project useful, consider starring the repo!

