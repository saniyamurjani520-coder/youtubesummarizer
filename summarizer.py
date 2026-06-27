import heapq
import re
from collections import Counter

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your",
    "yours", "yourself", "yourselves",
}


def tokenize_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def tokenize_words(text: str) -> list[str]:
    return [word.lower() for word in re.findall(r"\b[a-zA-Z0-9']+\b", text) if word.lower() not in STOP_WORDS]


def summarize_text(text: str, style: str = "brief") -> str:
    """
    Summarize text with simple extractive method. Styles: 'brief', 'detailed', 'bullets'.
    """
    if not text:
        return "No transcript available."

    sentences = tokenize_sentences(text)
    if not sentences:
        return "Unable to summarize the transcript."

    # style -> number of sentences
    style_map = {
        "brief": 2,
        "detailed": 8,
        "bullets": 5,
    }
    max_sentences = style_map.get(style, 3)

    if len(sentences) <= max_sentences:
        result = " ".join(sentences)
        if style == "bullets":
            return "\n- " + "\n- ".join(sentences)
        return result

    words = tokenize_words(text)
    if not words:
        return "Unable to summarize the transcript."

    frequency = Counter(words)
    max_freq = max(frequency.values())
    for word in frequency:
        frequency[word] /= max_freq

    sentence_scores = {}
    for sentence in sentences:
        score = 0
        for word in tokenize_words(sentence):
            score += frequency.get(word, 0)
        if score > 0:
            sentence_scores[sentence] = score

    best_sentences = heapq.nlargest(max_sentences, sentence_scores, key=sentence_scores.get)
    if style == "bullets":
        return "\n- " + "\n- ".join(best_sentences)
    return " ".join(best_sentences)
