"""TF-IDF + LogisticRegression baseline on a tiny inline dataset (the real PROMISE file is used in eval/)."""

import pytest

from app.nlp.classify import FUNCTIONAL, NON_FUNCTIONAL, load_promise_nfr, predict, promise_label, train_baseline

FUNCTIONAL_TEXTS = [
    "The system shall allow the user to create an order.",
    "The system shall let the admin delete a customer account.",
    "The system shall send an SMS when the parcel is out for delivery.",
    "The system shall allow the dispatcher to reassign a delivery.",
    "The system shall let the user download the report as a PDF.",
    "The system shall allow customers to track their order.",
]
NON_FUNCTIONAL_TEXTS = [
    "The system shall load every page within 2 seconds.",
    "The system shall respond to searches within 1 second under normal load.",
    "The system shall encrypt all passwords and personal data.",
    "The system shall be available 99.9 percent of the time.",
    "The system shall be easy to use for first-time users.",
    "The system shall support 1000 concurrent users without slowing down.",
]


def test_train_and_predict():
    model = train_baseline(FUNCTIONAL_TEXTS + NON_FUNCTIONAL_TEXTS, [FUNCTIONAL] * 6 + [NON_FUNCTIONAL] * 6)

    results = predict(model, ["The system shall allow the user to cancel an order.", "Pages shall load within 3 seconds."])

    assert [label for label, _ in results] == [FUNCTIONAL, NON_FUNCTIONAL]
    assert all(0.5 <= p <= 1 for _, p in results)


@pytest.mark.parametrize("cls, label", [("F", FUNCTIONAL), (" f ", FUNCTIONAL), ("PE", NON_FUNCTIONAL), ("SE", NON_FUNCTIONAL)])
def test_promise_label(cls, label):
    assert promise_label(cls) == label


def test_load_promise_csv(tmp_path):
    path = tmp_path / "promise_nfr.csv"
    path.write_text(
        "ProjectID,RequirementText,_class_\n"
        "1,'The system shall refresh the display every 60 seconds.',PE\n"
        '1,"The system shall let the user add, edit and remove a product.",F\n'
        "2,,F\n",
        encoding="utf-8",
    )

    texts, labels = load_promise_nfr(path)

    assert texts == [
        "The system shall refresh the display every 60 seconds.",
        "The system shall let the user add, edit and remove a product.",
    ]
    assert labels == [NON_FUNCTIONAL, FUNCTIONAL]


def test_load_rejects_unknown_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="class column"):
        load_promise_nfr(path)
