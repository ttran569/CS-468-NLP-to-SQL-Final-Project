# SETUP.md — Train Your Own NLP → SQL Model (Gemma 3 + LoRA)

This guide walks you through building your own **Natural Language to SQL system** using a custom dataset and fine-tuning **Gemma 3 (1B)** with **LoRA**.

---

## 1. Prerequisites

### Hardware
- GPU recommended (T4 / A100 / RTX 30+)
- Minimum: 12GB VRAM (for 4-bit training)

### Software
- Python 3.10+
- CUDA-compatible PyTorch

Install dependencies:
```bash
pip install transformers datasets peft trl bitsandbytes unsloth
```

---

## 2. Prepare Your Dataset

Your dataset should follow this structure:

```json
{
  "question": "Find all books after 2000",
  "context": "CREATE TABLE books (id INT, title TEXT, publication_year INT);",
  "answer": "SELECT title FROM books WHERE publication_year > 2000"
}
```

### Tips
- Include realistic schemas (multiple tables, foreign keys)
- Cover joins, filters, aggregations
- Avoid overly long examples (>512 tokens)

---

## 3. Preprocess Data

```python
from datasets import load_dataset

# Load your dataset
# Replace with your file or Hugging Face dataset

dataset = load_dataset("json", data_files="your_data.json")

# Shuffle & split
dataset = dataset["train"].shuffle(seed=3407)
split = dataset.train_test_split(test_size=0.05, seed=42)
train_data = split["train"]
test_data = split["test"]
```

### Format for Gemma

```python
def format_example(example):
    return {
        "text": f"""
Generate one SQL query using the schema below. Return only SQL.

Schema:
{example['context']}

Question: {example['question']}
"""
    }

train_data = train_data.map(format_example)
```

---

## 4. Load Base Model (Gemma 3)

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/gemma-3-1b-it",
    max_seq_length=512,
    load_in_4bit=True,
)
```

---

## 5. Apply LoRA Fine-Tuning

```python
from peft import get_peft_model

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_alpha=16,
    lora_dropout=0.05,
)
```

---

## 6. Train the Model

```python
from trl import SFTTrainer

trainer = SFTTrainer(
    model=model,
    train_dataset=train_data,
    dataset_text_field="text",
    max_seq_length=512,
)

trainer.train()
```

---

## 7. Evaluate Your Model

### Metrics to Use
- Exact Match
- Execution Accuracy (recommended)
- Syntax Error Rate

### Example Execution Test

```python
import sqlite3

conn = sqlite3.connect(":memory:")

# Load schema + data
conn.executescript(schema_sql)

# Run generated query
cursor = conn.execute(predicted_sql)
result = cursor.fetchall()
```

Compare results with ground truth SQL.

---

## 8. Inference (Generate SQL)

```python
prompt = """
Generate one SQL query using the schema below.

Schema:
[YOUR SCHEMA]

Question: List all users who joined after 2020
"""

inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=128)
print(tokenizer.decode(outputs[0]))
```

---

## 9. Best Practices

- Use **temperature = 0.0** for deterministic SQL
- Normalize outputs (lowercase, remove extra spaces)
- Validate queries before execution
- Add schema descriptions for better accuracy

---

## 10. Common Pitfalls

❌ Missing JOIN conditions  
❌ Incorrect GROUP BY usage  
❌ Hallucinated columns  
❌ Syntax errors (missing FROM, etc.)

---

## 11. Scaling Up

To improve performance:
- Increase dataset size (10k–20k+ examples)
- Add multiple schemas
- Include harder queries (nested queries, HAVING)
- Use batched inference

---

## 12. Deployment Ideas

- Web app (Streamlit / React)
- Chat-based SQL assistant
- BI tool integration

---

## Summary

By following this pipeline, you can build a **high-accuracy NLP-to-SQL system** tailored to your own database. Fine-tuning even a small model like Gemma 1B with LoRA can achieve strong performance with relatively low compute.

---

🚀 Tip: Start small, validate execution accuracy, then scale your dataset for best results.

