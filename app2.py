import easyocr
import cv2
import argparse
from spellchecker import SpellChecker
import time
import os
import numpy as np

def preprocess_image(image_path):
    """Preprocess the image to improve OCR results and speed"""
    # Read the image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image from {image_path}")
    
    # Resize image if it's too large (maintain aspect ratio)
    max_dimension = 1200
    height, width = image.shape[:2]
    if max(height, width) > max_dimension:
        scale = max_dimension / max(height, width)
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = cv2.resize(image, (new_width, new_height))
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply adaptive thresholding to handle different lighting conditions
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY, 11, 2)
    
    # Denoise the image
    denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
    
    return denoised

def extract_text_from_document(image_path, use_gpu=False, lang='en'):
    """
    Extract text from a document image with optimized performance
    
    Args:
        image_path (str): Path to the document image
        use_gpu (bool): Whether to use GPU acceleration
        lang (str): Language code for OCR
        
    Returns:
        str: Extracted text
    """
    start_time = time.time()
    
    # Initialize the OCR reader (only once)
    print("Initializing OCR engine...")
    reader = easyocr.Reader([lang], gpu=use_gpu, detector=True)
    
    # Preprocess the image
    print("Preprocessing image...")
    preprocessed_image = preprocess_image(image_path)
    
    # Extract text
    print("Extracting text...")
    results = reader.readtext(preprocessed_image)
    
    # Process results
    extracted_text = ""
    for detection in results:
        text = detection[1]
        extracted_text += text + " "
    
    processing_time = time.time() - start_time
    print(f"OCR completed in {processing_time:.2f} seconds")
    
    return extracted_text.strip()

def apply_spell_check(text):
    """Apply spell checking as a separate step"""
    print("Applying spell checking...")
    spell = SpellChecker()
    
    words = text.split()
    corrected_words = []
    
    # Process in batches to improve performance
    batch_size = 100
    for i in range(0, len(words), batch_size):
        batch = words[i:i+batch_size]
        
        for word in batch:
            # Only check alphabetic words above a minimum length
            if word.isalpha() and len(word) > 2:
                corrected_word = spell.correction(word)
                if corrected_word:
                    corrected_words.append(corrected_word)
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)
    
    return " ".join(corrected_words)

def main():
    parser = argparse.ArgumentParser(description="Optimized Medicine Package OCR")
    parser.add_argument("-i", "--image", default="C:\\Users\\priya\\Downloads\\Medicine_desp\\Medicine_desp\\medicine_back.webp", 
                        help="Path to the medicine package image")
    parser.add_argument("--gpu", action="store_true", help="Use GPU if available")
    parser.add_argument("--skip-spell-check", action="store_true", help="Skip spell checking to improve speed")
    
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.image):
        print(f"Error: Image file not found: {args.image}")
        return
    
    # Extract text
    start_time = time.time()
    extracted_text = extract_text_from_document(args.image, use_gpu=args.gpu)
    
    # Apply spell checking (optional)
    if not args.skip_spell_check:
        extracted_text = apply_spell_check(extracted_text)
    
    # Print the extracted text
    print("\n" + "="*50)
    print("EXTRACTED TEXT:")
    print("="*50)
    print(extracted_text)
    print("="*50)
    
    # Save to file
    with open('extracted_text.txt', 'w', encoding='utf-8') as f:
        f.write(extracted_text)
    print(f"Text saved to 'extracted_text.txt'")
    
    total_time = time.time() - start_time
    print(f"Total processing time: {total_time:.2f} seconds")

if __name__ == "__main__":
    main()