"""Baseline classifier: functional vs non-functional with TF-IDF + LogisticRegression (BUILD_PLAN Step 5).

Not used by the extraction pipeline (the LLM classifies there). It is the baseline the LLM is compared with
in evaluation (eval/scripts/eval_classification.py), trained on the PROMISE NFR dataset in
eval/data/promise_nfr.csv. Works on English requirement text only.
"""

import csv
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

FUNCTIONAL = "functional"
NON_FUNCTIONAL = "non_functional"

# Column names used by the different PROMISE NFR CSV exports
TEXT_COLUMNS = ("RequirementText", "requirement_text", "text", "requirement")
CLASS_COLUMNS = ("_class_", "class", "Class", "label")


def promise_label(promise_class: str) -> str:
    """PROMISE class "F" is functional; every other class (PE, SE, US, A, ...) is non-functional."""
    return FUNCTIONAL if promise_class.strip().upper() == "F" else NON_FUNCTIONAL


def load_promise_nfr(path: str | Path) -> tuple[list[str], list[str]]:
    """Requirement texts and functional/non_functional labels from a PROMISE NFR CSV file."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        text_col = next((c for c in TEXT_COLUMNS if c in columns), None)
        class_col = next((c for c in CLASS_COLUMNS if c in columns), None)
        if text_col is None or class_col is None:
            raise ValueError(f"{path}: needs a requirement text column and a class column, found {columns}")
        texts, labels = [], []
        for row in reader:
            text = (row[text_col] or "").strip().strip("'").strip()
            if text and (row[class_col] or "").strip():
                texts.append(text)
                labels.append(promise_label(row[class_col]))
    return texts, labels


def train_baseline(texts: list[str], labels: list[str]) -> Pipeline:
    model = Pipeline(
        [
            ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    model.fit(texts, labels)
    return model


def predict(model: Pipeline, texts: list[str]) -> list[tuple[str, float]]:
    """(label, probability of that label) for each text."""
    classes = list(model.classes_)
    return [(classes[row.argmax()], float(row.max())) for row in model.predict_proba(texts)]
