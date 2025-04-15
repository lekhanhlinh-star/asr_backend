import re

import wordninja


def repair_en_sticky_word(sent):
    records = []
    for match in re.finditer("[a-zA-Z]+", sent):
        start = match.start()
        end = match.end()

        segment = match.group()
        fixed_seg = wordninja.split(segment)

        records.append((segment, " ".join(fixed_seg)))
    
    new_sent = sent
    for record in records:
        new_sent = new_sent.replace(*record)
        
    return new_sent