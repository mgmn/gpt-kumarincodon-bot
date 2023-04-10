import re

def remove_tags(str):
    return re.sub(r'<[^>]+>', '', str)

def remove_first_accts_id(str):
    return re.sub(r'^(?:\s*@(\w+)\s+)+', '', str)

def escape_acct_at(str):
    return re.sub(r'@(?=\w)', "[@]", str)
