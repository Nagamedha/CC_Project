import decimal
import html
import os
import re
import unicodedata
from typing import List
from bs4 import BeautifulSoup
from word2number import w2n
from symspellpy import SymSpell, Verbosity
current_dir = os.path.dirname(os.path.abspath(__file__))
resources_dir = os.path.join(current_dir, 'resources')

# Currency and multiplier references
CURRENCY_KEYWORDS = {
    "dollar", "dollars", "usd", "rupee", "rupees", "rs", "rs.", "inr", "inr.", "₹", "$", "bucks"
}

# Common Indian multipliers, plus others
MULTIPLIERS = {
    "hundred", "thousand", "million", "billion",
    "lakh", "lakhs", "lac", "lacs", "crore", "crores"
}

MULTIPLIER_MAP = {
    "ten": 1e1,
    "hundred": 1e2,
    "thousand": 1e3,
    "lakh": 1e5,
    "lakhs": 1e5,
    "lac": 1e5,
    "lacs": 1e5,
    "million": 1e6,
    "crore": 1e7,
    "crores": 1e7,
    "billion": 1e9,
}

ABBREVIATIONS_MAP = {
    r"\bqty\b": "quantity",
    r"\bmrp\b": "maximum retail price",
    r"\bmfg\b": "manufacturing",
    r"\bexp\b": "expiry",
    r"\bgst\b": "goods and services tax",
    r"\bamt\b": "amount",
    r"\bdob\b": "date of birth",
    r"\bupi\b": "unified payments interface",
    r"\bsms\b": "message",
    r"\bod\b": "outstanding",
    r"\bemis?\b": "equated monthly installment",
    r"\bcust(?:omer)?\b": "customer",
}

# ▶ NEW BFSI & ADDRESS EXPANSIONS:
#   Merge them inside _expand_abbreviations after the original map
BFSI_ADDRESS_ABBREV = {
    r"\bacc?\b": "account",
    r"\bifsc\b": "indian financial system code",
    r"\bkyc\b": "know your customer",
    r"\bpan\b": "permanent account number",
    r"\bhno\b": "house number",
    r"\bs/o\b": "son of",
}

# ▶ Additional Abbreviation Enhancements
ABBREVIATIONS_MAP.update({
    r"\btxn\b": "transaction",
    r"\bref\b": "reference",
    r"\bac(?:count)?\.?\b": "account",
    r"\bamt\.?\b": "amount",
    r"\bcrm\b": "customer relationship management"
})

UNIT_SYNONYMS = {
    r"\bpcs\b": "pieces",
    r"\bnos\b": "units",
    r"\bltr\b": "liters",
    r"\bkg\b": "kilograms",
    r"\bgms?\b": "grams",
    r"\bml\b": "milliliters",
    r"\bdozen\b": "12 units",
}

DATE_REGEX = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]??\d{2,5}[-.\s]??\d{2,5}[-.\s]??\d{2,9})|(\+91\s?\d{10})", re.IGNORECASE)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
URL_REGEX = re.compile(r"(https?://\S+)|(www\.\S+)", re.IGNORECASE)

# ▶ NEW: PAN & Aadhaar placeholders
PAN_REGEX = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
AADHAR_REGEX = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b", re.IGNORECASE)

# ▶ NEW: Account numbers, TXN IDs, Reference codes
ACCOUNT_NO_REGEX = re.compile(r"\b\d{9,18}\b")
TXN_REGEX = re.compile(r"\bTXN[\w\d]+\b", re.IGNORECASE)
REF_REGEX = re.compile(r"\bRef[:\-]?\s?[A-Z0-9]{6,}\b", re.IGNORECASE)

# ▶ NEW: Remove RTF control symbols and unicode blobs
RTF_CONTROL_REGEX = re.compile(r"(\\[a-z]+\d*|{\\\*\\[^}]+}|[{}])")
UNICODE_UC0U_REGEX = re.compile(r"uc0u\d+")
UNICODE_UXXXX_REGEX = re.compile(r"u\d{4}")

# ▶ NEW: IFSC, duplicate numbers, font noise, spacing cleanup
IFSC_REGEX = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
FONT_HEADER_REGEX = re.compile(r"^(Helvetica;[\s;]*)", re.IGNORECASE)
DUPLICATE_CURRENCY_REGEX = re.compile(r"\b(\d{5,})(?:[\s,]+)(?:\d{1,3},\d{2,3},\d{3})\s*₹?")
PERMANENT_NUMBER_NOISE_REGEX = re.compile(r"permanent account number\s+Number", re.IGNORECASE)
COLON_SPACING_REGEX = re.compile(r"\s*:\s*")
sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
sym_spell.load_dictionary(os.path.join(resources_dir, "frequency_dictionary_en_82_765.txt"), term_index=0, count_index=1)
sym_spell.load_dictionary(os.path.join(resources_dir, "custom_indian_business_dict.txt"), term_index=0, count_index=1)

class TextPreprocessor:
    """
    Optimized Preprocessor for unstructured business text suited for
    Indian SMB contexts and general NLP tasks (SpaCy, Sentiment, TF-IDF).
    """

    @staticmethod
    def preprocess(
        text: str,
        convert_words: bool = True,
        remove_emojis: bool = True,
        replace_with_placeholders: bool = False
    ) -> str:
        """
        Preprocesses raw text to preserve linguistic context for NLP models.

        Args:
            text (str): Raw input text.
            convert_words (bool): Convert number words to digits (e.g., 'ten thousand' → '10000').
            remove_emojis (bool): If True, remove emojis entirely;
                                  else keep them or replace them with <EMOJI> placeholders.
            replace_with_placeholders (bool): If True, phone numbers, emails, and URLs
                                              are replaced with placeholders <PHONE>, <EMAIL>, <URL>.

        Returns:
            str: Cleaned and normalized text.
        """
        # 1. Decode HTML entities
        text = html.unescape(text)

        # 2. Remove HTML tags
        text = BeautifulSoup(text, "lxml").get_text()

        # 3. Normalize Unicode characters (handles multilingual text)
        text = unicodedata.normalize("NFKC", text)

        # ▶ NEW: Remove RTF control words and unicode blobs
        text = RTF_CONTROL_REGEX.sub("", text)
        text = UNICODE_UC0U_REGEX.sub("", text)
        text = UNICODE_UXXXX_REGEX.sub("", text)

        # ▶ NEW: Strip unwanted font headers and formatting noise
        text = FONT_HEADER_REGEX.sub("", text)

        # 4. Optionally remove or replace emojis
        if remove_emojis:
            # Remove non-ASCII symbols that might be emojis
            text = re.sub(r"[^\w\s.,!?$₹:;'\-\/\"@]", "", text)
        else:
            # Alternatively, replace them with <EMOJI> placeholders
            # (simple approach: anything in the "So" unicode category or beyond typical ASCII)
            text = re.sub(r"[\U00010000-\U0010ffff]+", "<EMOJI>", text)

        # 5. Replace or remove phone numbers, emails, and URLs
        if replace_with_placeholders:
            # Replace PAN and Aadhaar before phone to prevent over-masking
            text = PAN_REGEX.sub("<PAN>", text)
            text = AADHAR_REGEX.sub("<AADHAAR>", text)
            text = TXN_REGEX.sub("<TXN_ID>", text)
            text = REF_REGEX.sub("Ref: <REF_NO>", text)
            text = IFSC_REGEX.sub("<IFSC>", text)
            text = ACCOUNT_NO_REGEX.sub("<ACCOUNT_NO>", text)

            # Then replace phones, emails, URLs (to avoid over-masking IDs)
            text = PHONE_REGEX.sub("<PHONE>", text)
            text = EMAIL_REGEX.sub("<EMAIL>", text)
            text = URL_REGEX.sub("<URL>", text)

        # 6. Normalize or unify currency abbreviations
        text = TextPreprocessor._normalize_currencies(text)
        #TODO: apply correct spelling (for better results)
        ## text = TextPreprocessor._correct_spelling(text)
        ##Before expansion
        emails = re.findall(EMAIL_REGEX, text)
        for i, email in enumerate(emails):
            text = text.replace(email, f"<EMAIL_{i}>")
        text = TextPreprocessor._expand_abbreviations(text)
        # After expansion
        for i, email in enumerate(emails):
            text = text.replace(f"<EMAIL_{i}>", email)
        text = TextPreprocessor._normalize_units(text)
        text = DATE_REGEX.sub("<DATE>", text)

        # ▶ NEW: Remove duplicate currency values like "25000000 2,50,00,000 ₹" → "₹25000000"
        text = DUPLICATE_CURRENCY_REGEX.sub(r"₹\1", text)
        # ▶ NEW: Remove duplicate currency values like "25000000 2,50,00,000 ₹" → "₹25000000"
        text = re.sub(r"\b(\d{6,})\s+(?:\d{1,3},\d{2},\d{3})\s*₹?", r"₹\1", text)
        text = re.sub(r"₹\s?\d{1,3}(?:,\d{2,3}){2,}", "", text)
        text = re.sub(r"\b��\s?\d{1,3}(?:,\d{2,3}){2,}\b", "", text)
        # 7. Remove or unify repeated punctuation (e.g., "!!!" → "!")
        text = re.sub(r"([!?.,])\1+", r"\1", text)

        # 8. Optionally remove unwanted symbols but keep essential punctuation
        # Keep: . , ! ? : ; ' " - / $ ₹
        # Also keep @ if we have <EMAIL> placeholders
        text = re.sub(r"[^a-zA-Z0-9\s.,!?$₹:;'\-\/\"@<>%()+-]", "", text)
        text = re.sub(r"[^\w\s.,!?$₹:;'\-\/\"@<>%()#+=]", "", text)
        text = re.sub(r"(?<=[a-zA-Z0-9])([:!?])(?=\s|$)", r" \1", text)
        # 9. Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # ▶ NEW: Fix colon spacing and verbose placeholder wording
        text = PERMANENT_NUMBER_NOISE_REGEX.sub("permanent account number", text)

        # 10. Encode to UTF-8 and decode back (normalize encoding)
        text = text.encode("utf-8").decode("utf-8")

        # 11. Convert number words to digits
        if convert_words:
            text = TextPreprocessor._advanced_word_to_num(text)

        # 12. (Optional) Remove repeated consecutive words
        #     e.g. "hello hello hello" → "hello"
        text = TextPreprocessor._remove_repeated_words(text)
        text = TextPreprocessor.final_cleanup(text)
        return text

    @staticmethod
    def _normalize_currencies(text: str) -> str:
        """
        Converts various currency references to a standardized form (optional).
        For instance:
            - 'Rs.', 'rs', 'rupees' → '₹'
            - 'dollars', 'USD' → '$'
        Adjust to your domain if you prefer 'INR' or something else.
        """
        # Simple approach: define small dictionary for expansions
        currency_map = {
            r"\brs\.\b": "₹",
            r"\brs\b": "₹",
            r"\brupees\b": "₹",
            r"\brupee\b": "₹",
            r"\binr\b": "₹",
            r"\binr\.\b": "₹",
            r"\bdollars?\b": "$",
            r"\busd\b": "$",
            r"\bbucks\b": "$"
        }
        # Replace each pattern with standard symbol
        for pattern, repl in currency_map.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _expand_abbreviations(text: str) -> str:
        for pattern, repl in ABBREVIATIONS_MAP.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

        # ▶ NEW BFSI & ADDRESS expansions
        for pattern, repl in BFSI_ADDRESS_ABBREV.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def _normalize_units(text: str) -> str:
        for pattern, repl in UNIT_SYNONYMS.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _remove_repeated_words(text: str) -> str:
        """
        Reduces consecutive duplicate words to a single instance.
        e.g. "hello hello hello, how are you?" -> "hello, how are you?"
        """
        words = text.split()
        if not words:
            return text

        filtered = [words[0]]
        for i in range(1, len(words)):
            if words[i].lower() != words[i - 1].lower():
                filtered.append(words[i])

        return " ".join(filtered)

    @staticmethod
    def _advanced_word_to_num(text: str) -> str:
        """
        Converts numeric phrases (e.g., "ten thousand rupees", "15 crore")
        into digits (e.g., "10000 rupees", "150000000").
        Handles Indian and international multipliers, and digit+multiplier combos.
        """
        words = text.split()
        result_words = []
        skip_until = -1

        i = 0
        while i < len(words):
            if i <= skip_until:
                i += 1
                continue

            # Case 1: Digit + Multiplier (e.g., ₹15 crore, $10 billion)
            if i + 1 < len(words):
                raw_number = words[i].strip(",.!?;:'\"")

                # Check for leading currency symbol
                currency_symbol = ""
                number_str = raw_number
                if raw_number.startswith(("₹", "$")):
                    currency_symbol = raw_number[0]
                    number_str = raw_number[1:]

                if re.match(r"^\d+(\.\d+)?$", number_str):
                    multiplier_word = words[i + 1].lower().strip(",.!?;:'\"")
                    if multiplier_word in MULTIPLIER_MAP:
                        try:
                            number = decimal.Decimal(number_str) * decimal.Decimal(MULTIPLIER_MAP[multiplier_word])
                            result_words.append(f"{currency_symbol}{int(number)}")
                            skip_until = i + 1
                            i += 2
                            continue
                        except Exception:
                            pass  # fallback to word-based logic

            # Case 2: Word-based numeric phrases (e.g., "ten crore")
            phrase, length = TextPreprocessor._parse_numeric_phrase(words, i)

            if length > 1:
                # We found a multi-word numeric phrase we can parse
                result_words.append(str(phrase))
                skip_until = i + length - 1
                i += length
            else:
                # Case 3: Single-word numeric conversion (e.g., "five")
                try:
                    converted = w2n.word_to_num(words[i])
                    result_words.append(str(converted))
                except ValueError:
                    result_words.append(words[i])
                i += 1

        return " ".join(result_words)

    @staticmethod
    def _parse_numeric_phrase(words: List[str], start_idx: int) -> (int, int):
        """
        Parse a potential multi-word numeric expression starting at 'start_idx'.
        Returns (numeric_value, phrase_length).
        If no multi-word numeric phrase is found, returns (None, 1).

        This is a simplistic approach; you'll want to refine for more complex grammar.
        """
        buffer = []
        idx = start_idx
        numeric_value = 0
        current_number = 0
        multiplier_applied = False

        while idx < len(words):
            w = words[idx].lower().strip(",.!?;:'\"")

            if w in MULTIPLIER_MAP:
                if current_number == 0:
                    current_number = 1  # handle "crore" alone meaning "1 crore"
                numeric_value += current_number * MULTIPLIER_MAP[w]
                current_number = 0
                multiplier_applied = True
                idx += 1
            else:
                try:
                    current_number += w2n.word_to_num(w)
                    idx += 1
                except ValueError:
                    break

        if multiplier_applied or numeric_value > 0:
            numeric_value += current_number
            return int(numeric_value), idx - start_idx

        return None, 1

    @staticmethod
    def _is_numeric_word_or_multiplier(word: str) -> bool:
        """
        Returns True if `word` is either:
          - a valid single-word number recognized by w2n (like "twenty", "five")
          - a recognized Indian multiplier (lakh, crore, etc.)
          - a recognized English multiplier (thousand, million, etc.)
        """
        # Quick attempt: if w2n can parse it alone, it's numeric
        try:
            _ = w2n.word_to_num(word)
            return True
        except ValueError:
            pass

        return word in MULTIPLIERS
    @staticmethod
    def _correct_spelling(text: str) -> str:
        corrected_tokens = []
        # ✅ Tokenize into words and punctuation
        tokens = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        for token in tokens:
            # ✅ Keep punctuation and symbols as-is
            if re.fullmatch(r"[^\w\s]", token):
                corrected_tokens.append(token)
                continue
            # ✅ Skip special tokens (contains digits, symbols, or mixed cases)
            if not token.isalpha():
                corrected_tokens.append(token)
                continue
            # ✅ Skip very short words
            if len(token) < 3:
                corrected_tokens.append(token)
                continue
            # ✅ Lookup spelling correction
            suggestions = sym_spell.lookup(token, Verbosity.TOP, max_edit_distance=2)
            if suggestions and suggestions[0].term.lower() != token.lower():
                corrected_tokens.append(suggestions[0].term)
            else:
                corrected_tokens.append(token)
        # ✅ Smart join (preserve sentence structure and punctuation)
        final_text = ""
        for i, token in enumerate(corrected_tokens):
            if i > 0 and not re.fullmatch(r"[^\w\s]", token):
                final_text += " "
            final_text += token
        return final_text

    @staticmethod
    def final_cleanup(text: str) -> str:
        # 1. Remove extra spaces before punctuation like ! ? : ; ,
        text = re.sub(r"\s+([?!:;,])", r"\1", text)

        # 2. Fix space after opening brackets/quotes and before closing
        text = re.sub(r"\(\s+", "(", text)
        text = re.sub(r"\s+\)", ")", text)
        text = re.sub(r'"\s+', '"', text)
        text = re.sub(r'\s+"', '"', text)

        # 3. Remove space before periods (edge case fix)
        text = re.sub(r"\s+\.", ".", text)

        # 4. Normalize multiple spaces
        text = re.sub(r"\s{2,}", " ", text)

        # 5. Capitalize sentence starts (basic, works for most cases)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        text = ' '.join(sentence.capitalize() for sentence in sentences)

        # 6. Final strip
        return text.strip()