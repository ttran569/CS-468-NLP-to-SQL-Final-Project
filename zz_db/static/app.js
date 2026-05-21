const MODEL_NAME = "hf.co/rahul042/gemma_3_finetune:Q8_0";
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

const $ = (id) => document.getElementById(id);

function formatValue(value) {
  if (typeof value === "number") return number.format(value);
  if (value === null || value === undefined) return "";
  return String(value);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Something went wrong.");
  return payload;
}

function renderBars(node, rows, labelKey, valueKey) {
  const max = Math.max(...rows.map((row) => Number(row[valueKey]) || 0), 1);
  node.innerHTML = rows
    .map((row, index) => {
      const value = Number(row[valueKey]) || 0;
      const palette = ["#2f6f4e", "#d8902f", "#c7653f", "#879f73"];
      return `
        <div class="bar-row">
          <span>${row[labelKey]}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(value / max) * 100}%; background:${palette[index % palette.length]}"></div></div>
          <strong>${currency.format(value)}</strong>
        </div>
      `;
    })
    .join("");
}

function renderRisk(rows) {
  $("riskList").innerHTML = rows
    .map(
      (row) => `
        <div class="risk-item">
          <span>${row.churn_risk}</span>
          <strong>${row.stores} stores</strong>
        </div>
      `
    )
    .join("");
}

function renderTable(node, rows) {
  if (!rows.length) {
    node.innerHTML = "<tbody><tr><td>No rows returned.</td></tr></tbody>";
    return;
  }
  const columns = Object.keys(rows[0]);
  node.innerHTML = `
    <thead><tr>${columns.map((column) => `<th>${column.replaceAll("_", " ")}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows
        .map((row) => `<tr>${columns.map((column) => `<td>${formatValue(row[column])}</td>`).join("")}</tr>`)
        .join("")}
    </tbody>
  `;
}

async function loadDashboard() {
  const data = await api("/api/metrics");
  $("totalMrr").textContent = currency.format(data.cards.total_mrr);
  $("avgMrr").textContent = currency.format(data.cards.avg_mrr);
  $("under25").textContent = data.cards.under_25k;
  $("avgNps").textContent = Math.round(data.cards.avg_nps);
  renderBars($("regionBars"), data.regions, "region", "mrr");
  renderBars($("categoryBars"), data.categories, "category", "revenue");
  renderRisk(data.risk);

  const sample = await api("/api/sample-data");
  renderTable($("storesTable"), sample.stores);
  renderTable($("transactionsTable"), sample.transactions);
}

async function checkModel() {
  try {
    const status = await api("/api/model-status");
    setModelReady(status.installed);
  } catch (error) {
    $("modelStatus").textContent = "Ollama is not reachable yet.";
  }
}

function setModelReady(installed) {
  const button = $("pullModel");
  if (installed) {
    $("modelStatus").textContent = "Model is installed locally.";
    button.disabled = true;
    button.textContent = "Model ready";
    return;
  }
  $("modelStatus").textContent = "Model is not installed yet.";
  button.disabled = false;
  button.textContent = "Pull model";
}

async function pullModel() {
  const button = $("pullModel");
  if (button.disabled && button.textContent === "Model ready") return;
  button.disabled = true;
  button.textContent = "Pulling...";
  $("modelStatus").textContent = "Downloading model through Ollama.";
  try {
    const result = await api("/api/pull-model", { method: "POST" });
    if (result.ok) {
      setModelReady(true);
    } else {
      $("modelStatus").textContent = result.output || "Ollama returned an error. Check terminal output.";
      button.disabled = false;
      button.textContent = "Pull model";
    }
  } catch (error) {
    $("modelStatus").textContent = error.message;
    button.disabled = false;
    button.textContent = "Pull model";
  } finally {
    if (button.textContent !== "Model ready") button.disabled = false;
  }
}

async function runInsight() {
  const question = $("question").value.trim();
  const button = $("runQuery");
  const error = $("queryError");
  error.classList.add("hidden");
  $("answer").classList.add("hidden");
  button.disabled = true;
  button.textContent = "Running...";
  try {
    const result = await api("/api/query", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    $("summary").textContent = `${result.summary} ${result.row_count} row${result.row_count === 1 ? "" : "s"} returned.`;
    $("sqlBlock").textContent = result.sql;
    renderTable($("resultTable"), result.rows);
    $("answer").classList.remove("hidden");
  } catch (err) {
    error.textContent = err.message;
    error.classList.remove("hidden");
  } finally {
    button.disabled = false;
    button.textContent = "Run insight";
  }
}

document.addEventListener("click", (event) => {
  const example = event.target.closest("[data-question]");
  if (example) $("question").value = example.dataset.question;
});

$("runQuery").addEventListener("click", runInsight);
$("pullModel").addEventListener("click", pullModel);
$("modelName").textContent = MODEL_NAME;

loadDashboard().catch((error) => {
  $("queryError").textContent = error.message;
  $("queryError").classList.remove("hidden");
});
checkModel();
