import re

# 文字列を count 字に納まるようにいいかんじに分割する
def split_context(str, count):
    return merge_paragraphs(split_to_paragraphs(str), count)

# 段落を count 字以内で結合する
def merge_paragraphs(paragraphs, count):
    result1 = []
    result2 = []
    para = ""

    # count 字をこえる段落を文単位で分割する
    for paragraph in paragraphs:
        if len(paragraph) > count:
            result1.extend(merge_sentences(split_to_sentences(paragraph), count))
            continue
        result1.append(paragraph)

    for paragraph in result1:
        if len(para + paragraph) > count:
            result2.append(para)
            para = ""
        para += paragraph
    if len(para) > 0:
        result2.append(para)

    # 段落の前後のゴミを取り除く
    for i in range(len(result2)):
        result2[i] = result2[i].strip()

    return result2

# 文字列を段落で分割する
def split_to_paragraphs(str):
    result = []
    paragraphs = str.split("\n\n")
    isInCodeblock = False
    codeblock = ""
    # 分割した各段落を結果配列に加えていく
    for para in paragraphs:
        # コードブロックが分割されてる場合は復元する
        if not isInCodeblock and para.startswith("```\n"):
            isInCodeblock = True
        # コードブロックのなかにいる
        if isInCodeblock:
            codeblock += para
            # コードブロックから出たとき
            if para.endswith("\n```"):
                isInCodeblock = False
                result.append(codeblock + "\n\n")
                codeblock = ""
            continue
        # /コードブロックのなかにいる
        if len(para) > 0:
            result.append(para + "\n\n")
    return result

# 文字列を文単位で count 字以内に結合する
def merge_sentences(sentences, count):
    result1 = []
    result2 = []
    para = ""

    # count 字をこえる文を単語単位で分割する
    for sentence in sentences:
        if len(sentence) > count:
            result1.extend(merge_words(split_to_words(sentence), count))
            continue
        result1.append(sentence)

    for sentence in result1:
        if len(para + sentence) > count:
            result2.append(para)
            para = ""
        para += sentence
    if len(para) > 0:
        result2.append(para)
    return result2

# 文字列を文単位で分割する
def split_to_sentences(str):
    result = []
    sentences = re.split(r"(?<=[\.\?!]\s)|(?<=[。？！])|(?<=\n)", str)
    # 分割した各文を結果配列に加えていく
    for sentence in sentences:
        if len(sentence) > 0:
            result.append(sentence)
    return result

# 文字列を単語単位で count 字以内に結合する
def merge_words(words, count):
    result1 = []
    result2 = []
    para = ""

    # count 字をこえる単語を無条件に分割する
    for word in words:
        if len(word) > count:
            result1.extend(split_force(word, count))
            continue
        result1.append(word)

    for word in result1:
        if len(para + word) > count:
            result2.append(para)
            para = ""
        para += word
    if len(para) > 0:
        result2.append(para)
    return result2

# 文字列を単語単位で分割する
def split_to_words(str):
    result = []
    words = re.split(r"\b", str)
    # 分割した各文を結果配列に加えていく
    for word in words:
        if len(word) > 0:
            result.append(word)
    return result

# 文字列を無条件に count 字以内に分割する
def split_force(str, count):
    result = []
    para = ""
    for char in str:
        if len(para + char) > count:
            result.append(para)
            para = ""
        para += char
    if len(para) > 0:
        result.append(para)
    return result
