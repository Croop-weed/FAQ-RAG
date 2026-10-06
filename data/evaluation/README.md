# Retrieval Evaluation Data

`sample_retrieval.jsonl` is a tiny synthetic demonstration dataset written against the fictional Orbit Desk sample FAQ corpus. Its five labeled queries validate the evaluation workflow only; results are not representative of customer traffic and must not be used to select a production embedding model.

A future golden dataset should target roughly 100-300 human-reviewed support queries, including paraphrases, typos, ambiguous and multi-intent questions, hard negatives, and unanswerable queries. Each JSONL row maps one stable query ID to one or more relevant FAQ IDs. Do not put real customer conversation data in this demo file.
