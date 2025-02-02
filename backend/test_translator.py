# test_translator.py

import pytest

# Skip the tests if PyTorch is not available
try:
    import torch
except ImportError:
    pytest.skip("PyTorch is not installed, skipping translator tests.", allow_module_level=True)

from transformers import pipeline
from api import translate_to_english  # Adjust the import if your translator function is located elsewhere

def test_translate_from_norwegian():
    # Instantiate the translation pipeline using the locally downloaded SeamlessM4T model.
    translator = pipeline(
        "translation",
        model="./local_model_dir/models--facebook--seamless-m4t-v2-large/snapshots/5f8cc790b19fc3f67a61c105133b20b34e3dcb76/",
        use_fast=False  # Force use of slow tokenizer to avoid Tiktoken conversion issues.
    )
    
    # Norwegian sample sentence
    norwegian_text = "Jeg føler meg veldig dårlig i dag."
    
    # Translate the text to English using your translator function
    translated_text = translate_to_english(norwegian_text, translator)
    
    # For debugging purposes, print the input and translation
    print("Original (Norwegian):", norwegian_text)
    print("Translated (English):", translated_text)
    
    # Assertions to verify the output:
    # 1. Ensure the translation returns a string.
    assert isinstance(translated_text, str)
    
    # 2. The translation should not equal the original text.
    assert translated_text != norwegian_text
    
    # 3. Verify that common Norwegian words do not appear in the output.
    assert "jeg" not in translated_text.lower()
    assert "meg" not in translated_text.lower()
    
    # 4. Check for an indication of English output. For example, the pronoun "I" is common in English.
    assert "I " in translated_text or "I" in translated_text