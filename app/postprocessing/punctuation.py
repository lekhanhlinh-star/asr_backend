#!/usr/bin/python3
"""
@Po-Kai 2023/12

ChinesePunctuation is a tool for restore the punctuation in chinese which maybe conatins some . 
"""
import re

from punctuators.models import PunctCapSegModelONNX
from transformers import AutoModelForTokenClassification,AutoTokenizer
import torch
from torch.utils.data import DataLoader
from zhpr.predict import DocumentDataset,merge_stride, decode_pred


class ChinesePunctuation(object):

    def __init__(self):
        model_name = 'p208p2002/zh-wiki-punctuation-restore'
        self.model = AutoModelForTokenClassification.from_pretrained(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.punc_list = ["，", "、", "。", "？", "！", "；"]

    def predict_step(self, batch):
        batch_out = []
        batch_input_ids = batch
    
        encodings = {'input_ids': batch_input_ids}
        output = self.model(**encodings)
    
        predicted_token_class_id_batch = output['logits'].argmax(-1)
        for predicted_token_class_ids, input_ids in zip(predicted_token_class_id_batch, batch_input_ids):
            out=[]
            tokens = self.tokenizer.convert_ids_to_tokens(input_ids)
            
            input_ids = input_ids.tolist()
            try:
                input_id_pad_start = input_ids.index(self.tokenizer.pad_token_id)
            except:
                input_id_pad_start = len(input_ids)
            input_ids = input_ids[:input_id_pad_start]
            tokens = tokens[:input_id_pad_start]
    
            predicted_tokens_classes = [self.model.config.id2label[t.item()] for t in predicted_token_class_ids]
            predicted_tokens_classes = predicted_tokens_classes[:input_id_pad_start]
    
            for token,ner in zip(tokens,predicted_tokens_classes):
                out.append((token,ner))
            batch_out.append(out)
            
        return batch_out
    
    def restore(self, text, window_size=256, step=200):
        en_words = set(re.findall("[a-zA-Z]+", text))
        text = text.replace(" ", "<s>")
        dataset = DocumentDataset(text.lower(), window_size=window_size, step=step)
        dataloader = DataLoader(dataset=dataset,shuffle=False,batch_size=5)

        model_pred_out = []
        for batch in dataloader:
            batch_out = self.predict_step(batch)
            for out in batch_out:
                model_pred_out.append(out)
            
        merge_pred_result = merge_stride(model_pred_out,step)
        merge_pred_result_deocde = decode_pred(merge_pred_result)
        merge_pred_result_deocde = ''.join(merge_pred_result_deocde)
        merge_pred_result_deocde = merge_pred_result_deocde.replace("[UNK]", "")
        merge_pred_result_deocde = merge_pred_result_deocde.replace("<s>", " ")
        for word in en_words:
            if word.lower() in merge_pred_result_deocde:
                merge_pred_result_deocde = merge_pred_result_deocde.replace(word.lower(), word)
        
        return merge_pred_result_deocde

    def __call__(self, text, end_punc="。"):
        restored = self.restore(text)
        if restored and restored[-1] not in self.punc_list:
            restored += end_punc   
        return restored


class EnglishPunctuation(object):
    
    def __call__(self, text, end_punc="。"):
        return text # by pass, using whisper prompt do it
       

class OthersPunctuation(object):
    
    def __init__(self):
        self.model = PunctCapSegModelONNX.from_pretrained("pcs_47lang")

    def __call__(self, text, end_punc="。"):
        results = self.model.infer(texts=[text], apply_sbd=True)
        return re.sub("(?i)<unk>", "", " ".join(results[0]))

    
punc_model_table = {
    "zh": ChinesePunctuation(),
    "en": EnglishPunctuation(),
}
other_punctuation = OthersPunctuation() # japanese is work well!


def add_punctuation(text, language):
    if language in punc_model_table:
        return punc_model_table[language](text)
    else:
        return other_punctuation(text)

