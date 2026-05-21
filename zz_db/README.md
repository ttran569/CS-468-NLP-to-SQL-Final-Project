# OperatorIQ

Local business-manager insights dashboard powered by SQLite and Ollama.

## Run

```bash
cd ~/Desktop/zz_db
python3 app.py
```

Open [http://localhost:8765](http://localhost:8765).

## Model

The dashboard is wired to:

```text
hf.co/rahul042/gemma_3_finetune:Q8_0
```

Use the **Pull model** button in the sidebar, or run:

```bash
ollama pull hf.co/rahul042/gemma_3_finetune:Q8_0
```

## Database

The app creates `business_insights.sqlite` automatically with four tables:

- `stores` - 125 rows
- `customers` - 125 rows
- `products` - 125 rows
- `transactions` - 125 rows

Generated SQL is automatically executed, but the server only permits read-only `SELECT` statements.
