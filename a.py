import re

def find_longest_paragraph(text_path):
    try:
        with open(text_path, 'r') as file:
            text = file.read()
            # Normalizar saltos de línea
            text = text.replace('\r', '\n')
            print(repr(text))
            # paragraphs = text.split('\n\n')
            
            # # Limpiar párrafos
            # paragraphs = [re.sub(r'\s+', ' ', p.strip()) for p in paragraphs if p.strip()]
            
            # if not paragraphs:
            #     return 0, ""
            
            # longest_paragraph = max(paragraphs, key=len)
            # print(f"Longest paragraph: {longest_paragraph}")
            # print(f"Length: {len(longest_paragraph)}")
            # return len(longest_paragraph), longest_paragraph

    except FileNotFoundError:
        print(f"Error: File not found at {text_path}")
        return 0, ""
    except Exception as e:
        print(f"Error reading text file: {e}")
        return 0, ""

# Call the function with your text file
find_longest_paragraph("/Users/matiasboldrini/Downloads/vdoc.pub_proceedings-of-the-1990-international-tesla-symposium_compressed.txt")
