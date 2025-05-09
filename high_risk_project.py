# -*- coding: utf-8 -*-
"""high_risk_project.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1U46apkvQU3-3sxDtlKF4mK5znzl4RzEN

# Fact or Fiction? Detecting Health Misinformation with AI
*High Risk Project, uaa99*
"""

# created for AI in Healthcare, Spring 2025

# dependencies
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer, AutoTokenizer, AutoModel
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from tqdm import tqdm
import numpy as np
import wandb
wandb.init(mode='disabled')

"""## Part 1: Model Selection and Preparation

We're going to be evaluating three baseline models for detecting misinformation:

BERT, Clinical-BERT, and MedLlama. We're going to use HuggingFace to access all three models.
"""

bertSeqClass = AutoModelForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=3, force_download=True)
bertSeqTokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')

clinicalBert = AutoModelForSequenceClassification.from_pretrained("emilyalsentzer/Bio_ClinicalBERT", num_labels=3, force_download=True)
clinicalBertTokenizer = AutoTokenizer.from_pretrained("emilyalsentzer/Bio_ClinicalBERT")

bioMedBert = AutoModelForSequenceClassification.from_pretrained("microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext", num_labels=3, force_download=True)
bioMedBertTokenizer = AutoTokenizer.from_pretrained("microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext")

bioLMTokenizer = AutoTokenizer.from_pretrained("stanford-crfm/BioMedLM")
bioLMModel = AutoModelForSequenceClassification.from_pretrained("stanford-crfm/BioMedLM", num_labels=3, force_download=True)

"""## Part 2: Data Loading and Preparation
Let's begin by loading up the data we are going to need to train and evaluate our models. We are going to be using the Covid 19 News Rumors dataset from [A COVID-19 Rumor Dataset](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2021.644801/full), published in Frontiers in Psychology.
"""

# load data
path_to_data = "/content/drive/MyDrive/AI in Healthcare final project/news.csv"
df = pd.read_csv(path_to_data, header=None, names=['id', 'label', 'text', 'sentiment'])
df.head()

# map the string labels to integer labels
label_map = {'F': 0, 'T': 1, 'U': 2, 'U(Twitter)': 2}
df['label'] = df['label'].map(lambda x: label_map.get(x))
df.head()

print(df['label'].value_counts())

# create train test split
train_texts, val_texts, train_labels, val_labels = train_test_split(
    df['text'].tolist(),
    df['label'].tolist(),
    test_size=0.2,
    random_state=42
)

# create custom pytorch dataset
class MisinformationDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item

    def __len__(self):
        return len(self.labels)

"""## Part 3: Model Training"""

def get_training_args(num_epochs):
  return TrainingArguments(
    output_dir=None,
    num_train_epochs=num_epochs,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=64,
    warmup_steps=100,
    weight_decay=0.01,
    logging_dir='./logs',
    eval_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
    metric_for_best_model='accuracy',
    learning_rate=2e-5,
    lr_scheduler_type='linear',
    report_to="none"
  )

def compute_metrics(p):
    predictions, labels = p
    predictions = predictions.argmax(axis=-1)
    accuracy = accuracy_score(labels, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average='weighted') # Use 'weighted' for multiclass
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
    }

def get_trainer(model, tokenizer, training_args):
  if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = model.config.eos_token_id

  train_encodings = tokenizer(train_texts, truncation=True, padding=True)
  val_encodings = tokenizer(val_texts, truncation=True, padding=True)

  train_dataset = MisinformationDataset(train_encodings, train_labels)
  val_dataset = MisinformationDataset(val_encodings, val_labels)

  return Trainer(
      model=model,
      args=training_args,
      train_dataset=train_dataset,
      eval_dataset=val_dataset,
      compute_metrics=compute_metrics,
  )

# init trainers
training_args = get_training_args(15)
bert_trainer = get_trainer(bertSeqClass, bertSeqTokenizer, training_args)
clinical_bert_trainer = get_trainer(clinicalBert, clinicalBertTokenizer, training_args)
bio_bert_trainer = get_trainer(bioMedBert, bioMedBertTokenizer, training_args)
bio_med_trainer = get_trainer(bioLMModel, bioLMTokenizer, training_args)

# train
trainers = {
    "BERT": bert_trainer,
    "ClinicalBERT": clinical_bert_trainer,
    "BioBERT": bio_bert_trainer,
    "BioMedLM": bio_med_trainer
}

for name, trainer in trainers.items():
  print(f'starting training {name}')
  trainer.train()
  torch.cuda.empty_cache()
  print(f'done training {name}')

bio_med_trainer.train()


"""## Part 4: Evaluating Performance"""

import json

bert_results = bert_trainer.evaluate()

clinical_bert_results = clinical_bert_trainer.evaluate()

print("Bert Evaluation Results:", json.dumps(bert_results, indent=4))

print("ClinicalBert Evaluation Results:", json.dumps(clinical_bert_results, indent=4))

if __name__ == "__main__":
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        df['text'].tolist(),
        df['label'].tolist(),
        test_size=0.2,
        random_state=42
    )

    bio_med_trainer = get_trainer(bioLMModel, bioLMTokenizer, training_args)
    bioLMTokenizer = AutoTokenizer.from_pretrained("stanford-crfm/BioMedLM")
    bioLMModel = AutoModelForSequenceClassification.from_pretrained("stanford-crfm/BioMedLM", num_labels=3,
                                                                    force_download=True)
    bio_med_trainer.train()