# ExamForge AI — Automated Question Paper Generation System with Bloom's Taxonomy Mapping for CBSE/State Boards

An end-to-end Machine Learning educational platform that automates cognitive test generation aligned with Bloom’s Revised Taxonomy and difficulty balancing for CBSE and State Board curricula.

---

## 📌 Features & Architectural Highlights

1. **Dual Machine Learning Pipelines**:
   - **Model A (Bloom's Taxonomy Classifier)**: 6-Class text classification (`Remember`, `Understand`, `Apply`, `Analyze`, `Evaluate`, `Create`) using TF-IDF sublinear vectorization and multiclass Logistic Regression.
   - **Model B (Difficulty Classifier)**: 3-Tier classification (`Easy`, `Medium`, `Hard`) evaluating question linguistic and cognitive complexity.
2. **Deterministic Constraint-Based Selection**:
   - Precise filtering across subjects, topics, question types, and target Bloom/difficulty distributions.
   - Exact question count and total marks sum validation.
3. **Automated PDF Compilation**:
   - ReportLab generation engine producing board-compliant printable examination papers with instructions and mark allocations.
4. **Interactive SaaS Dashboard (8 Pages)**:
   - **Overview Dashboard**: High-level system statistics, workflow architecture, and live models status.
   - **Generate Question Paper**: Interactive configuration form with sliders for target Bloom and difficulty distributions.
   - **Paper Preview**: A4-styled preview with direct PDF download.
   - **Question Bank**: Searchable, paginated repository with Bloom/difficulty filters and modal to add teacher-verified questions.
   - **AI Classification**: Real-time NLP inference tool for arbitrary question text with class probability distribution.
   - **Model Performance**: Full evaluation suite showing accuracy, precision, recall, macro F1, and per-class metrics.
   - **Generation History**: Persisted database archive of all previous question papers.
   - **Settings & System**: Real-time service connectivity and health monitor.

---

## 🗄️ Dataset Source & License

- **Source Dataset**: `Uzaib52/edubloom-question-bank` (Hugging Face)
- **License**: MIT License
- **Total Questions Cleaned & Normalized**: 73,712 questions across 11 disciplines (Physics, Chemistry, Mathematics, Computer Science, Biology, Economics, History, Accounting, Psychology, Geography, Artificial Intelligence).

---

## 🚀 Getting Started & Execution

### 1. Prerequisites
- Python 3.10+
- Node.js 18+

### 2. Backend Setup & Startup
```bash
cd backend
pip install -r requirements.txt

# Start Flask REST API server (runs on http://localhost:5000)
python app.py
```

### Local Candidate Model Training (VS Code / PowerShell)

The cleaned Hugging Face dataset is already available at
`backend/data/questions_dataset.csv`. Use this local copy by default; no dataset
download or question-bank import is required for classifier training. Candidate
models and evaluation reports receive unique timestamped names. This workflow
does not replace the active production models unless `--activate` is explicitly
passed.

```powershell
Set-Location 'C:\Users\iniya\OneDrive\Desktop\mini project'
& .\.venv\Scripts\Activate.ps1

# Fast local run on a stratified subset; omit --sample-limit for all 73,712 rows.
python .\train_local.py --task all --source csv --sample-limit 6000 --n-estimators 30

# Review the newest Bloom and difficulty held-out evaluation reports.
Get-ChildItem .\backend\reports\rf-*-candidate-local-v*_evaluation.json |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 2 |
  ForEach-Object { Get-Content $_.FullName -Raw }

# Test candidate inference (replace the sample question as needed).
$bloomCandidate = Get-ChildItem .\backend\models\rf-bloom-candidate-local-v*.joblib |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 -ExpandProperty FullName
python .\train_local.py --task bloom --predict-candidate $bloomCandidate --question "Explain how evaporation changes liquid water into water vapor."

$difficultyCandidate = Get-ChildItem .\backend\models\rf-difficulty-candidate-local-v*.joblib |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 -ExpandProperty FullName
python .\train_local.py --task difficulty --predict-candidate $difficultyCandidate --question "Explain how evaporation changes liquid water into water vapor."
```

Training metrics are internal held-out evaluations of this dataset, not proof of
curriculum alignment or generalization to unseen boards. EduBloom remains
General / EduBloom data and does not become verified Tamil Nadu State Board
material through training.

### 3. Frontend Setup & Startup
```bash
cd frontend
npm install
npm run dev
# Accessible at http://localhost:5173
```

### 4. Running Verification Test Suite
```bash
cd backend
python -m unittest tests/test_system.py -v
```

---

## 🔐 Authentication & Demonstration Credentials

ExamForge AI includes a centered login portal inspired by modern academic portals with JWT token verification and PBKDF2 password hashing.

### Demo Account (Auto-provisioned on startup)
- **Email**: `teacher@examforge.ai`
- **Password**: `ExamForge@2026`

*(The login screen also features a 1-click **"Fill Demo Credentials"** assistant button for convenience during college presentations).*

### Protected Endpoints & Route Access
- `/login` — Public authentication portal
- `/dashboard` — Protected overview and assessment analytics
- `/generate-paper` — Protected paper blueprint configurator
- `/question-bank` — Protected question repository
- `/classification` — Protected real-time ML inference
- `/model-performance` — Protected Scikit-Learn evaluation metrics
- `/history` — Protected exam archive and PDF downloads

---

## 📊 Evaluation Summary

- **Bloom's Classifier**: Tested on 14,743 held-out test questions. Accuracy: ~39.1%, Macro F1: ~35.4% (natural lexical overlap between subtle cognitive categories documented in `backend/reports/bloom_evaluation.json`).
- **Difficulty Classifier**: Tested on 14,743 held-out test questions. Accuracy: 100.0%, Macro F1: 100.0%.
- Both model pipelines saved in `backend/models/*.joblib`.
