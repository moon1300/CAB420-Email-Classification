# CAB420-Email-Classification
The goal of the project is to classify Enron emails based on who sent them using machine learning techniques. The model takes the text/content of an email and predicts the sender of the email. This is a multi-class text classification problem using natural language processing (NLP).

## Downloading Dataset
Download the Enron email dataset from:

https://www.cs.cmu.edu/~enron/ 
(May 7, 2015 Version of dataset) and place locally in data/maildir/

## Workflow Rules
Before working:
- git pull
- After changes:
- git add .
- git commit -m "notes eg. added SVM preprocessing"
- git push

## NOTE for NOTEBOOKS
Do NOT all edit the same notebook.
Instead:
one notebook per method
shared preprocessing scripts in /src
to avoid clashes when notebooks save metadata differently.
